from enum import StrEnum
from typing import Any, ClassVar, cast

from pydantic import BaseModel, ConfigDict, Field, create_model

DEFAULT_PAGE = 1
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

RESERVED_FIELDS = frozenset({'page', 'limit', 'search', 'ordering'})


class SearchType(StrEnum):
    ILIKE = 'ilike'
    EXACT = 'exact'


def _alias_generator(field_name: str) -> str:
    if field_name in RESERVED_FIELDS:
        return field_name
    return f'filter[{field_name}]'


def _build_ordering_enum(name: str, fields: tuple[str, ...]) -> type[StrEnum]:
    members = {}
    for field in fields:
        key = field.upper()
        members[key] = field
        members[f'{key}_DESC'] = f'-{field}'
    return cast('type[StrEnum]', StrEnum(f'{name}Ordering', members))


class QueryParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_alias_generator)

    page: int = Field(DEFAULT_PAGE, ge=1)
    limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)

    @classmethod
    def build(
        cls,
        name: str,
        filters: type[BaseModel] | None = None,
        ordering_fields: tuple[str, ...] | None = None,
        default_ordering: str | None = None,
        search_fields: dict[str, SearchType] | None = None,
    ) -> type['QueryParams']:
        field_definitions = {}

        if filters:
            for field_name, field_info in filters.model_fields.items():
                field_definitions[field_name] = (field_info.annotation, field_info.default)

        if ordering_fields:
            if not default_ordering:
                raise ValueError('default_ordering is required when ordering_fields is provided')
            if default_ordering.lstrip('-') not in ordering_fields:
                raise ValueError(f"default_ordering '{default_ordering}' must be one of {ordering_fields}")
            ordering_enum = _build_ordering_enum(name, ordering_fields)
            field_definitions['ordering'] = (ordering_enum, default_ordering)

        if search_fields:
            field_definitions['search'] = (str | None, None)
            field_definitions['search_fields'] = (ClassVar[dict[str, SearchType]], search_fields)

        return create_model(name, __base__=cls, **field_definitions)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit

    @property
    def filters(self) -> dict[str, Any]:
        return {
            field_name: getattr(self, field_name)
            for field_name in self.model_fields
            if field_name not in RESERVED_FIELDS and getattr(self, field_name) is not None
        }
