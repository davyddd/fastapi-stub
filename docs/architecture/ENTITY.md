## Entity

**Entity** is a domain object identified by a unique property (typically a primary key).
It represents a single record in a database table and encapsulates related data and behavior.

**Constraints:**
1. **Unique identity** — one-to-one correspondence with a database record via primary key.
2. **Field consistency** — Entity fields should align with the database schema (ORM model).
3. **PK naming** — primary key inherits from `AutoUUID` and named `{entity}_id`. Use `default_factory` for auto-generation.
4. **No date fields** — do not add `created_at` / `updated_at` to Entity unless needed in business logic.
ORM handles these via `DatesMixin`.

**Example:**
```python
from pydantic import EmailStr, Field

from dddesign.components.domains.value_objects import AutoUUID
from dddesign.structure.domains.entities import Entity


class ProfileId(AutoUUID):
    ...


class Profile(Entity):
    profile_id: ProfileId = Field(default_factory=ProfileId)
    first_name: str | None
    last_name: str | None
    email: EmailStr

    @property
    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip()
```

### Change Tracking

Use `dddesign.utils.base_model.TrackChangesMixin` to track field modifications.
Provides `has_changed` property — returns `True` if any field was modified.
Use in Repository to skip database calls when no fields have changed.

### Updating from DTO

Use `update(data, exclude_fields)` method to update entity fields from DTO.
Updates only fields that exist in both entity and DTO.

```python
entity.update(data, exclude_fields={'device_info'})
```