import base64
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import md5
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import false, inspect as sqlalchemy_inspect
from sqlmodel import SQLModel, and_, func, or_
from sqlmodel.ext.asyncio.session import AsyncSession

from ddutils.datetime_helpers import utc_now

from share.pagination.cursor import decode_cursor, encode_cursor
from share.sqlmodel.filter_params import FilterParams
from share.sqlmodel.lookups import LOOKUP_SEPARATOR, Lookup, SearchType
from share.sqlmodel.models.mixins.dates import UpdatedDateMixin
from share.sqlmodel.update_params import UpdateParams


def _build_lookup_condition(column: Any, lookup: Lookup, value: Any) -> Any:
    if lookup is Lookup.ISNULL:
        return column.is_(None) if value else column.is_not(None)
    if lookup is Lookup.IN:
        return column.in_(value)
    if isinstance(value, list):
        raise ValueError("List values are only allowed with the 'in' lookup")
    return column == value


class FilterSet(BaseModel):
    """Executes a `FilterParams` contract against the database.

    `select()` returns the page objects together with both boundary cursors,
    `count()` returns the number of matching rows, `update_by_filters()` applies an
    `UpdateParams` contract. Statements are built internally: filters, search, and
    keyset paging whose composite key is always the effective ordering plus the
    model's primary key.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session: AsyncSession
    model: type[SQLModel]
    base_statement: Any
    params: FilterParams
    extra_columns: dict[str, Any] = Field(default_factory=dict)

    # --- building blocks ---

    def _resolve_column(self, field_name: str) -> Any:
        return self.extra_columns[field_name] if field_name in self.extra_columns else getattr(self.model, field_name)

    def _apply_filters(self, statement: Any) -> Any:
        # Filter fields are `<column>` or `<column>__<lookup>` — see `FilterParams`.
        for field_name, value in self.params.values.items():
            column_name, _, lookup_name = field_name.partition(LOOKUP_SEPARATOR)
            column = self._resolve_column(column_name)
            statement = statement.where(_build_lookup_condition(column, Lookup(lookup_name or Lookup.EXACT), value))
        return statement

    def _apply_search(self, statement: Any) -> Any:
        search_fields = type(self.params).search_fields
        if not self.params.search or not search_fields:
            return statement
        conditions = []
        for field_name, search_type in search_fields.items():
            column = getattr(self.model, field_name)
            if search_type is SearchType.ILIKE:
                conditions.append(column.ilike(f'%{self.params.search}%'))
            elif search_type is SearchType.EXACT:
                # Coerce the term into the column type (e.g. UUID): an uncastable term
                # simply cannot match this column, so its condition is skipped.
                try:
                    value = column.type.python_type(self.params.search)
                except (ValueError, TypeError):
                    continue
                conditions.append(column == value)
            else:
                raise ValueError(f"Search type '{search_type}' is not supported")
        if not conditions:
            # Every column rejected the term - nothing can match.
            return statement.where(false())
        return statement.where(or_(*conditions))

    # --- keyset key & cursor codec ---

    def _keyset_key(self) -> tuple[str, ...]:
        """The cursor's composite key: the effective ordering plus the model's primary
        key as a unique tiebreaker (appended unless the ordering already ends on it)."""
        ordering = self.params.ordering or type(self.params).default_ordering
        ordering_fields = type(self.params).ordering_fields
        if ordering and ordering_fields and ordering.lstrip('-') not in ordering_fields:
            raise ValueError(f"Ordering '{ordering}' is not one of {ordering_fields}")
        key = [ordering] if ordering else []
        primary_key = sqlalchemy_inspect(self.model).primary_key
        if len(primary_key) != 1:
            raise ValueError(f'Keyset paging requires a single-column primary key on {self.model.__name__}')
        pk = primary_key[0].name
        if pk not in {k.lstrip('-') for k in key}:
            key.append(pk)
        return tuple(key)

    def _key_fingerprint(self) -> str:
        return md5(','.join(self._keyset_key()).encode()).hexdigest()[:2]  # noqa: S324

    def _value_to_token(self, column: Any, value: Any) -> str:
        """Compact URL-safe token for a keyset value; `_token_to_value` is the inverse
        and derives the type from the same column."""
        python_type = column.type.python_type
        if issubclass(python_type, datetime):
            return str(int(value.timestamp() * 1_000_000))
        if issubclass(python_type, UUID):
            return value.hex
        if issubclass(python_type, str):
            return base64.urlsafe_b64encode(str(value).encode()).decode().rstrip('=')
        return str(value)

    def _token_to_value(self, column: Any, token: str) -> Any:
        python_type = column.type.python_type
        if issubclass(python_type, datetime):
            return datetime.fromtimestamp(int(token) / 1_000_000, tz=UTC)
        if issubclass(python_type, UUID):
            return UUID(token)
        if issubclass(python_type, str):
            return base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)).decode()
        return python_type(token)

    def _decoded_cursor(self) -> tuple[list[str] | None, bool]:
        if self.params.cursor is None:
            return None, False
        key = self._keyset_key()
        tokens, direction = decode_cursor(self.params.cursor, self._key_fingerprint(), len(key))
        return tokens, direction == 'prev'

    def _apply_keyset(self, statement: Any, anchor: list[str] | None, backwards: bool) -> Any:
        # A prev-cursor scans in reverse: every direction flips, and the predicate walks
        # strictly "before" the anchor; `select` flips the rows back.
        order_by = []
        seen_after_anchor = []
        equal_so_far: list[Any] = []
        for position, key in enumerate(self._keyset_key()):
            scan_descending = key.startswith('-') != backwards
            column = self._resolve_column(key.lstrip('-'))
            order_by.append(column.desc() if scan_descending else column.asc())
            if anchor is not None:
                value = self._token_to_value(column, anchor[position])
                strictly_after = column < value if scan_descending else column > value
                seen_after_anchor.append(and_(*equal_so_far, strictly_after) if equal_so_far else strictly_after)
                equal_so_far.append(column == value)
        if anchor is not None:
            # Lexicographic "strictly after the anchor" in scan order: differs on the
            # first key, or ties on it and differs on the second, and so on.
            statement = statement.where(or_(*seen_after_anchor))
        return statement.order_by(*order_by)

    def _boundary_tokens(self, row: Any) -> list[str]:
        tokens = []
        for key in self._keyset_key():
            field = key.lstrip('-')
            value = self._boundary_value(row, field)
            tokens.append(self._value_to_token(self._resolve_column(field), value))
        return tokens

    @staticmethod
    def _boundary_value(row: Any, field: str) -> Any:
        # A row is either a model instance / a Row with the column selected directly,
        # or a composite Row (entity + extra columns) — then the entity carries the field.
        if hasattr(row, field):
            return getattr(row, field)
        for item in row:
            if hasattr(item, field):
                return getattr(item, field)
        raise ValueError(f"Keyset field '{field}' is not present in the selected row")

    # --- public API ---

    async def select(self) -> tuple[Sequence[Any], str | None, str | None]:
        """One page of objects plus both boundary cursors.

        With `params.cursor` the page is anchored by the fast keyset path (a prev-cursor
        scans in reverse and is flipped back); without one it falls back to
        `OFFSET (page - 1) * page_size`. One extra row is over-fetched: it signals
        continuation on the scan side, the other side is implied by how we got here
        (a cursor, or a jump past page 1). Returns model instances when a single entity
        is selected, raw rows otherwise.
        """
        anchor, backwards = self._decoded_cursor()
        page_size = self.params.page_size

        statement = self._apply_filters(self.base_statement)
        statement = self._apply_search(statement)
        statement = self._apply_keyset(statement, anchor, backwards)
        if anchor is None and self.params.page > 1:
            statement = statement.offset(self.params.offset)
        statement = statement.limit(page_size + 1)

        result = await self.session.execute(statement)
        single_entity = len(statement.column_descriptions) == 1
        rows = list(result.scalars().all() if single_entity else result.all())

        overflow = len(rows) > page_size
        rows = rows[:page_size]
        if backwards:
            rows.reverse()
        if not rows:
            return rows, None, None

        fingerprint = self._key_fingerprint()
        next_exists = True if backwards else overflow
        prev_exists = overflow if backwards else (anchor is not None or self.params.page > 1)
        next_cursor = encode_cursor(fingerprint, self._boundary_tokens(rows[-1]), 'next') if next_exists else None
        prev_cursor = encode_cursor(fingerprint, self._boundary_tokens(rows[0]), 'prev') if prev_exists else None
        return rows, next_cursor, prev_cursor

    async def count(self) -> int:
        statement = self.base_statement.with_only_columns(func.count())
        statement = self._apply_filters(statement)
        statement = self._apply_search(statement)
        result = await self.session.execute(statement)
        return result.scalar() or 0

    async def update_by_filters(self, update_params: UpdateParams) -> None:
        """UPDATE from an Update base_statement: SET from the `UpdateParams` contract,
        WHERE from the filter fields of `params` (same logic as `select`)."""
        values = update_params.values
        if not values:
            raise ValueError('At least one update value must be provided')
        if issubclass(self.model, UpdatedDateMixin):
            values.setdefault('updated_at', utc_now())
        await self.session.execute(self._apply_filters(self.base_statement.values(**values)))
