## Adapter

**Adapter** is an infrastructure component that isolates interactions with external services.
Based on the Adapter Pattern from "Gang of Four" (GoF) — it bridges the interface of both systems.
Like Repository, Adapter is injected into Application as a dependency.

### Internal Adapter

**InternalAdapter** is used for integration with internal services (other contexts within the system).
Initially calls Applications directly; can be replaced with HTTP / gRPC / message bus later without changing the interface.

**Example:**
```python
from dddesign.structure.infrastructure.adapters.internal import InternalAdapter

from app.profile_context.applications.profile import profile_app_impl
from app.profile_context.domains.entities.profile import Profile


class ProfileAdapter(InternalAdapter):
    @staticmethod
    async def get(profile_id: ProfileId) -> Profile:
        profile = await self.profile_app.get(profile_id)
        return Profile.model_validate(profile)


profile_adapter_impl = ProfileAdapter()
```

### External Adapter

**ExternalAdapter** is used for integration with third-party APIs (Apple, Google, payment providers, etc.).

**Example:**
```python
import httpx
from dddesign.structure.infrastructure.adapters.external import ExternalAdapter

from app.purchase_context.domains.dto.transaction_history import TransactionHistory


class AppleAdapter(ExternalAdapter):
    @staticmethod
    async def get_history_transactions(transaction_id: str) -> TransactionHistory:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'https://api.storekit.itunes.apple.com/inApps/v1/history/{transaction_id}'
            )
            response.raise_for_status()
            return TransactionHistory.model_validate(response.json())


apple_adapter_impl = AppleAdapter()
```
