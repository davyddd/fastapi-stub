from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import SQLModel, func, or_
from sqlmodel.sql._expression_select_cls import Select, SelectOfScalar

from share.pagination import QueryParams
from share.pagination.query_params import SearchType


class FilterSet(BaseModel):
    model: type[SQLModel]
    query_params: QueryParams
    base_statement: Any
    extra_columns: dict[str, Any] = Field(default_factory=dict)

    def _apply_filters(self, statement: Select | SelectOfScalar) -> Select | SelectOfScalar:
        for field_name, value in self.query_params.filters.items():
            column = self.extra_columns[field_name] if field_name in self.extra_columns else getattr(self.model, field_name)
            statement = statement.where(column.in_(value)) if isinstance(value, list) else statement.where(column == value)
        return statement

    def _apply_search(self, statement: Select | SelectOfScalar) -> Select | SelectOfScalar:
        search = getattr(self.query_params, 'search', None)
        search_fields = getattr(self.query_params, 'search_fields', None)
        if not search or not search_fields:
            return statement
        conditions = []
        for field_name, search_type in search_fields.items():
            column = getattr(self.model, field_name)
            if search_type == SearchType.ILIKE:
                conditions.append(column.ilike(f'%{search}%'))
            elif search_type == SearchType.EXACT:
                conditions.append(column == search)
            else:
                raise ValueError(f"Search type '{search_type}' is not supported")
        return statement.where(or_(*conditions))

    def _apply_ordering(self, statement: Select | SelectOfScalar) -> Select | SelectOfScalar:
        ordering = getattr(self.query_params, 'ordering', None)
        if ordering:
            ordering = str(ordering)
            desc = ordering.startswith('-')
            col_name = ordering.lstrip('-')
            column = getattr(self.model, col_name)
            return statement.order_by(column.desc() if desc else column.asc())
        return statement

    def _apply_range(self, statement: Select | SelectOfScalar) -> Select | SelectOfScalar:
        return statement.limit(self.query_params.limit).offset(self.query_params.offset)

    def select(self) -> Select | SelectOfScalar:
        statement = self.base_statement
        statement = self._apply_filters(statement)
        statement = self._apply_search(statement)
        statement = self._apply_ordering(statement)
        statement = self._apply_range(statement)
        return statement

    def count(self) -> Select | SelectOfScalar:
        statement = self.base_statement.with_only_columns(func.count())
        statement = self._apply_filters(statement)
        statement = self._apply_search(statement)
        return statement
