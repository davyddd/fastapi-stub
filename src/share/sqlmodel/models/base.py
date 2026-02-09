from typing import ClassVar, Generic, Self, Type, TypeVar, cast, get_args

from pydantic import BaseModel
from sqlalchemy.orm import declared_attr
from sqlmodel import MetaData, SQLModel

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


class BaseSQLModel(SQLModel, Generic[EntityT]):
    metadata = metadata

    _entity_class: ClassVar[Type[BaseModel]]

    @declared_attr  # type: ignore
    def __tablename__(cls) -> str:  # noqa: N805
        return convert_camel_case_to_snake_case(cls.__name__)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if kwargs.get('table'):
            entity_class = get_args(cls.__orig_bases__[0])[0]  # ty: ignore[unresolved-attribute]
            if entity_class is None or isinstance(entity_class, TypeVar):
                raise TypeError(
                    f'{cls.__name__} must specify entity type: ' f'class {cls.__name__}(BaseSQLModel[YourEntity], table=True)'
                )
            cls._entity_class = entity_class

    def to_entity(self) -> EntityT:
        return cast(EntityT, self._entity_class.model_validate(self, from_attributes=True))

    @classmethod
    def from_entity(cls, entity: EntityT) -> Self:
        return cls.model_validate(entity, from_attributes=True)
