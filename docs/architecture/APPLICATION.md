## Application

**Application** is a programmatic interface for accessing business logic.
It serves as the primary entry point for all domain operations.

Applications can be invoked from:
1. **Ports** — HTTP endpoints, background tasks (Dramatiq), CLI commands.
2. **Other Applications** — within the same Context, creating a layered structure.
3. **Internal Adapters** — for cross-context communication.

**Constraints:**
1. **Maximum one Repository per Application** — if you need more, create an additional subordinate Application.
2. **No direct SQL or external calls** — delegate to Repository / Adapter.
3. **Application orchestrates, not implements** — the correct sequence of calls is the business logic itself.
Transformations, conversions, and computations should be moved to Domain methods or Services.

### Hierarchy

Within a single Context, Applications can form a hierarchy:
- **Leading Application** — manages core business logic for a primary entity.
- **Subordinate Application** — handles narrower delegated tasks for related entities.

**Example:**
```text
ProfileApp (leading)
    └── DeviceInfoApp (subordinate)
```

`DeviceInfo` is not independent — it always belongs to a `Profile`.
Thus, `DeviceInfoApp` can only be called from `ProfileApp`, never directly from Ports.

**Example:**
```python
from dddesign.structure.applications import Application

from config.databases.postgres import Atomic


class ProfileApp(Application):
    repo: ProfileRepository = profile_repo_impl
    device_info_app: DeviceInfoApp = device_info_app_impl

    async def create(self, data: ProfileDTO) -> Profile:
        async with Atomic():
            profile = await self.repo.create(data)
            await self.device_info_app.create(profile.id, data.device_info)

        return profile


profile_app_impl = ProfileApp()
```

Transactions can be opened at the Application level to ensure atomicity — see [POSTGRES.md](../databases/POSTGRES.md#transactions).

### Application Factory

`ApplicationFactory` facilitates creating Application instances with specific dependencies.
Useful when multiple interfaces with different dependencies share the same application logic.

**Example:**
```python
from dddesign.structure.applications import Application, ApplicationDependencyMapper, ApplicationFactory


class AuthSocialApp(Application):
    account_app: AccountApp = account_app_impl
    social_account_app: SocialAccountApp = social_account_app_impl
    social_adapter: social.SocialAdapterInterface


auth_social_app_factory = ApplicationFactory[AuthSocialApp](
    application_class=AuthSocialApp,
    dependency_mappers=(
        ApplicationDependencyMapper(
            application_attribute_name='social_adapter',
            request_attribute_value_map={
                SocialDriver.APPLE: social.apple_id_adapter_impl,
                SocialDriver.GOOGLE: social.google_adapter_impl,
                SocialDriver.FACEBOOK: social.facebook_adapter_impl,
            },
        ),
    ),
)

# note: the argument name must match the lowercase version of the Enum class name
auth_apple_app_impl = auth_social_app_factory.get(social_driver=SocialDriver.APPLE)
```