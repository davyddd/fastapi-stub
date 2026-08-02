from enum import StrEnum
from typing import Any, ClassVar, cast

from pydantic import BaseModel, ConfigDict, Field, create_model

from share.sqlmodel.filter_params import DEFAULT_LIMIT, QUERY_FIELDS, FilterParams

DEFAULT_PAGE = 1
MAX_LIMIT = 100

RESERVED_FIELDS = frozenset({'page', 'limit', 'search', 'ordering', 'cursor'})


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
    """HTTP query contract of a list endpoint, built from a model's `FilterParams`:
    pagination, search, ordering, and flat `filter[...]`-aliased filter fields. Defined
    next to the route; the data-access side receives the `filter_params` projection.
    """

    model_config = ConfigDict(populate_by_name=True, alias_generator=_alias_generator)

    filter_params_class: ClassVar[type[FilterParams]] = FilterParams

    page: int = Field(DEFAULT_PAGE, ge=1)
    limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    # Keyset-paginated endpoints echo the previous page's next_cursor here; page/limit
    # endpoints simply never receive it.
    cursor: str | None = None

    @classmethod
    def build(cls, name: str, filter_params: type[FilterParams]) -> type['QueryParams']:
        field_definitions: dict[str, Any] = {
            'filter_params_class': (ClassVar[type[FilterParams]], filter_params),
        }

        for field_name, field_info in filter_params.model_fields.items():
            if field_name in QUERY_FIELDS:
                continue
            field_definitions[field_name] = (field_info.annotation, field_info.default)

        if filter_params.ordering_fields:
            ordering_enum = _build_ordering_enum(name, filter_params.ordering_fields)
            field_definitions['ordering'] = (ordering_enum, filter_params.default_ordering)

        if filter_params.search_fields:
            field_definitions['search'] = (str | None, None)

        return create_model(name, __base__=cls, **field_definitions)

    @property
    def filter_params(self) -> FilterParams:
        """The data-access projection of this query — what repositories work with."""
        filter_fields = {
            name: getattr(self, name)
            for name in self.filter_params_class.model_fields
            if name not in QUERY_FIELDS and name in type(self).model_fields
        }
        ordering = getattr(self, 'ordering', None)
        return self.filter_params_class(
            **filter_fields,
            ordering=str(ordering) if ordering else None,
            search=getattr(self, 'search', None),
            limit=self.limit,
            page=self.page,
            cursor=self.cursor,
        )
