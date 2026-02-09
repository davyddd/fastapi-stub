## Value Object

**Value Object** is an object defined solely by its properties, with no unique identifier.
Introduced in "Domain-Driven Design" by Eric Evans to reduce domain model complexity.

**Constraints:**
1. **No identity** — identified by attributes, not a unique identifier.
2. **Immutability** — cannot be modified after creation, ensuring consistency.
3. **Equality** — two Value Objects are equal if all their properties match.

**Example:**
```python
from dddesign.structure.domains.value_objects import ValueObject


class Money(ValueObject):
    amount: Decimal
    currency: str
```

Alternatively, you can create a custom Pydantic type without inheriting from `ValueObject`.
This is useful for simple single-value types.

**Example:**
```python
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema


class EmailStr:
    @classmethod
    def __get_pydantic_core_schema__(cls, _source: type[Any], _handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(cls._validate, core_schema.str_schema())

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        field_schema = handler(core_schema)
        field_schema.update(type='string', format='email')
        return field_schema

    @classmethod
    def _validate(cls, input_value: str, /) -> str:
        return validate_email(input_value)[1]
```