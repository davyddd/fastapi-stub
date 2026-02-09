## Naming

Naming conventions for classes, files and instances.

### Class Names

Class names must include an architectural suffix that reflects their role.

| Component | Pattern | Example |
|-----------|---------|---------|
| Application | `<Name>App` | `ProfileApp` |
| Repository | `<Name>Repository` | `ProfileRepository` |
| Adapter | `<Name>Adapter` | `AppleAdapter` |
| Service | `<Verb><Subject>Service` | `CalculateTaxService` |
| Entity / ValueObject | `<Name>` | `Profile`, `Money` |
| Aggregate | `<Name>Aggregate` | `ProfileAggregate` |
| DTO | `<Name>DTO` | `ProfileDTO` |

### File Names

File names use `snake_case` based on the main class, without architectural suffixes.

| File | Class |
|------|-------|
| `applications/profile.py` | `ProfileApp` |
| `repositories/profile.py` | `ProfileRepository` |
| `adapters/external/apple.py` | `AppleAdapter` |

Service file names should be nouns, not verbs. `CalculateTaxService` → `services/tax_calculator.py`.

### Factory Method

Use `factory` classmethod to create instances from other objects (commonly for Entity and Aggregate).

**Example:**
```python
class Profile(Entity):
    profile_id: ProfileId = Field(default_factory=ProfileId)
    first_name: str
    last_name: str
    email: EmailStr

    @classmethod
    def factory(cls, data: CreateProfileDTO) -> Self:
        return cls(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
        )
```

### Implementation Instances

Instances with `_impl` suffix must be created at module level for reusable components.

**Example:**
```python
class ProfileApp(Application):
    repo: ProfileRepository = profile_repository_impl
    device_info_app: DeviceInfoApp = device_info_app_impl

    ...


profile_app_impl = ProfileApp()
```

### Route Handlers

Route handler functions follow the pattern `<application>_<method>`.

| Application Method | Handler Function |
|--------------------|------------------|
| `ProfileApp.save` | `profile_save` |
| `TransactionEventApp.create` | `transaction_event_create` |

### URL Naming

URLs use `kebab-case` and follow a hierarchical structure.

**Structure:**
```
/api/v1/<context>/<resource>/<action>/
```

**Conventions:**
1. Context prefix is defined in `config/urls.py` (e.g., `/profile`, `/mailing`)
2. Resource and action prefixes are defined in `<context>/infrastructure/urls.py`
3. Use `kebab-case` for multi-word segments (e.g., `transaction-event`)
4. End URLs with trailing slash

**Example:**
```python
# config/urls.py
router = APIRouter(prefix='/api/v1')
router.include_router(profile_router, prefix='/profile', tags=['Profile'])

# profile_context/infrastructure/urls.py
router = APIRouter()
router.include_router(http.profile_router, prefix='/save')
router.include_router(http.transaction_event_router, prefix='/transaction-event/save')
```

Results in:
- `POST /api/v1/profile/save/`
- `POST /api/v1/profile/transaction-event/save/`