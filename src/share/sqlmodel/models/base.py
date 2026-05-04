from typing import Any, ClassVar, Generic, Self, Type, TypeVar, cast

from pydantic import BaseModel
from sqlalchemy.orm import declared_attr
from sqlmodel import MetaData, SQLModel
from sqlmodel.main import SQLModelMetaclass

from ddutils.convertors import convert_camel_case_to_snake_case

EntityT = TypeVar('EntityT', bound=BaseModel)

# https://alembic.sqlalchemy.org/en/latest/naming.html
NAMING_CONVENTION = {
    'all_column_names': lambda constraint, _table: '_'.join([column.name for column in constraint.columns.values()]),
    'ix': 'ix__%(table_name)s__%(all_column_names)s',
    'uq': 'uq__%(table_name)s__%(all_column_names)s',
    'ck': 'ck__%(table_name)s__%(constraint_name)s',
    'fk': 'fk__%(table_name)s__%(all_column_names)s__%(referred_table_name)s',
    'pk': 'pk__%(table_name)s',
}


metadata = MetaData(naming_convention=NAMING_CONVENTION)  # type: ignore


class BaseSQLModelMeta(SQLModelMetaclass):
    def __new__(cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs: Any) -> Any:
        new_cls = super().__new__(cls, name, bases, namespace, **kwargs)
        if kwargs.get('table') and not hasattr(new_cls, '_entity_class'):
            raise TypeError(f'{name} must specify entity type: ' f'class {name}(BaseSQLModel[YourEntity], table=True)')
        return new_cls


class BaseSQLModel(SQLModel, Generic[EntityT], metaclass=BaseSQLModelMeta):
    metadata = metadata

    _entity_class: ClassVar[Type[BaseModel]]

    @declared_attr  # type: ignore
    def __tablename__(cls) -> str:  # noqa: N805
        return convert_camel_case_to_snake_case(cls.__name__)

    def __class_getitem__(cls, params: type[Any] | tuple[type[Any], ...]) -> Any:  # type: ignore[invalid-method-override]
        result = super().__class_getitem__(params)
        if not isinstance(params, TypeVar):
            result._entity_class = params
        return result

    def to_entity(self) -> EntityT:
        data: dict[str, Any] = {}
        for field_name, field_info in self._entity_class.model_fields.items():
            if hasattr(self, field_name):
                data[field_name] = getattr(self, field_name)
                continue

            alias = field_info.alias
            if alias and hasattr(self, alias):
                data[field_name] = getattr(self, alias)

        return cast(EntityT, self._entity_class(**data))

    @classmethod
    def from_entity(cls, entity: EntityT) -> Self:
        return cls.model_validate(entity.model_dump(mode='json', by_alias=True))
