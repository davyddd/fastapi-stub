from typing import Any, ClassVar, get_args

from pydantic import BaseModel, create_model

from share.sqlmodel.lookups import LOOKUP_SEPARATOR, FieldLookups, Lookup, SearchType

DEFAULT_LIMIT = 20

# Instance fields of the query itself, not filter columns (see `values`).
QUERY_FIELDS = frozenset({'ordering', 'search', 'limit', 'page', 'cursor'})


class FilterParams(BaseModel):
    """Data-access query contract of a model: what can be filtered (and with which
    lookups), ordered by, searched on, plus the range. One subclass per model, built
    with `build` and located next to the repository that consumes it.

    `FilterSet` applies instances to SELECT/UPDATE statements. HTTP list endpoints
    wrap the same contract into a `QueryParams` (see share.pagination) and project it
    back via `QueryParams.filter_params`.
    """

    ordering_fields: ClassVar[tuple[str, ...]] = ()
    default_ordering: ClassVar[str | None] = None
    search_fields: ClassVar[dict[str, SearchType]] = {}

    ordering: str | None = None
    search: str | None = None
    limit: int | None = None
    page: int = 1
    # Opaque keyset cursor (see FilterSet.select_keyset); its composite key is always
    # the effective ordering plus the model's primary key as tiebreaker.
    cursor: str | None = None

    @classmethod
    def build(
        cls,
        name: str,
        filters: type[BaseModel] | None = None,
        ordering_fields: tuple[str, ...] | None = None,
        default_ordering: str | None = None,
        search_fields: dict[str, SearchType] | None = None,
    ) -> type['FilterParams']:
        if ordering_fields:
            if not default_ordering:
                raise ValueError('default_ordering is required when ordering_fields is provided')
            if default_ordering.lstrip('-') not in ordering_fields:
                raise ValueError(f"default_ordering '{default_ordering}' must be one of {ordering_fields}")

        field_definitions: dict[str, Any] = {
            'ordering_fields': (ClassVar[tuple[str, ...]], tuple(ordering_fields or ())),
            'default_ordering': (ClassVar[str | None], default_ordering),
            'search_fields': (ClassVar[dict[str, SearchType]], search_fields or {}),
            'ordering': (str | None, default_ordering),
        }
        if filters:
            for field_name, field_info in filters.model_fields.items():
                field_definitions.update(_expand_lookups(field_name, field_info))
        return create_model(name, __base__=cls, **field_definitions)

    @property
    def page_size(self) -> int:
        return self.limit or DEFAULT_LIMIT

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def values(self) -> dict[str, Any]:
        """Non-empty filter fields only (query fields like ordering/search excluded)."""
        return {field_name: value for field_name, value in self if field_name not in QUERY_FIELDS and value is not None}


def _expand_lookups(field_name: str, field_info: Any) -> dict[str, Any]:
    """One field per declared lookup: EXACT keeps the field as declared; IN becomes
    `<field>__in: list[...]`; ISNULL becomes `<field>__isnull: bool`."""
    field_lookups = next((meta for meta in field_info.metadata if isinstance(meta, FieldLookups)), None)
    if field_lookups is None:
        return {field_name: (field_info.annotation, field_info.default)}

    base_type = _strip_none(field_info.annotation)
    definitions: dict[str, Any] = {}
    for lookup in field_lookups.lookups:
        if lookup is Lookup.EXACT:
            definitions[field_name] = (field_info.annotation, field_info.default)
        elif lookup is Lookup.IN:
            definitions[f'{field_name}{LOOKUP_SEPARATOR}{Lookup.IN}'] = (list[base_type] | None, None)  # type: ignore[valid-type]
        elif lookup is Lookup.ISNULL:
            definitions[f'{field_name}{LOOKUP_SEPARATOR}{Lookup.ISNULL}'] = (bool | None, None)
    return definitions


def _strip_none(annotation: Any) -> Any:
    args = tuple(arg for arg in get_args(annotation) if arg is not type(None))
    if not args:
        return annotation
    if len(args) == 1:
        return args[0]
    raise ValueError(f'Cannot derive a single base type from {annotation!r} for lookup expansion')
