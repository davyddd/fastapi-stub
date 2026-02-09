## Errors

Unified error handling based on `dddesign`. All errors are transformed into 4XX responses.

### Response Format

Errors are converted to JSON using `dddesign.components.domains.dto.Errors`.

FastAPI exception handlers:
- `handle_base_error` — handles `BaseError`
- `handle_collection_error` — handles `CollectionError`
- `handle_http_exception` — handles `HTTPException`
- `handle_request_validation_error` — handles `RequestValidationError`

**Example:**
```json
{
  "errors": [
    {
      "message": "Profile already exists",
      "error_code": "profile_already_exists_error",
      "status_code": 400,
      "field_name": null
    }
  ]
}
```

### BaseError

Use for single business-level errors. Located in `<context>/domains/errors/`.

**Example:**
```python
from dddesign.structure.domains.errors import BaseError


class ProfileAlreadyExistsError(BaseError):
    status_code: int = 400
    message: str = 'Profile already exists'


class ProfanityDetectedError(BaseError):
    status_code: int = 400
    message: str = 'Profanity detected in content'
```

### CollectionError

Use for aggregating multiple errors before raising.

**Example:**
```python
from dddesign.structure.domains.errors import BaseError, CollectionError


class ProfileApp(Application):
    repo: ProfileRepository = profile_repo_impl

    def create(self, data: ProfileDTO) -> Profile:
        errors = CollectionError()
        entity = Profile.factory(data)

        if self.repo.exists(email=entity.email):
            errors.add(ProfileAlreadyExistsError())

        if not ProfanityCheckService(content=entity.full_name).handle():
            errors.add(ProfanityDetectedError())

        if errors:
            raise errors

        ...


profile_app_impl = ProfileApp()
```

### wrap_error

Converts Pydantic `ValidationError` into `CollectionError`.

**Example:**
```python
from pydantic import ValidationError

from dddesign.structure.domains.errors import wrap_error

from app.profile_context.domains.dto.profile import ProfileDTO


try:
    profile_data = ProfileDTO(**data)
except ValidationError as e:
    raise wrap_error(e) from e
```

### create_pydantic_error_instance

Factory for creating Pydantic-like errors in `@field_validator` or `@model_validator`.

**Example:**
```python
from pydantic import field_validator

from dddesign.structure.domains.value_objects import ValueObject
from dddesign.utils.base_model import create_pydantic_error_instance


class Money(ValueObject):
    value: Decimal
    currency: str

    @field_validator('value')
    @classmethod
    def validate_value(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise create_pydantic_error_instance(
                base_error=ValueError,
                code='invalid_value',
                message='Value must be positive',
            )
        return value
```