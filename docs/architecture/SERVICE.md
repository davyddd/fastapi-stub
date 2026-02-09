## Service

**Service** handles business logic that cannot be naturally assigned to a single Domain object.
If a method could belong to multiple entities or doesn't fit any specific one, it should be extracted into a Service.

**Constraints:**
1. **No infrastructure dependencies** — must not depend on Application, Repository, or Adapter.
All required data is passed as arguments.
2. **Single method** — typically implements only one `handle` method.
3. **Pure logic** — deterministic results based solely on inputs, easy to unit test.

A Service can either return a new object or modify the input object in place.
If modifying in place, this should be clear from the method name or docstring.

**Example:**
```python
from pydantic import model_validator

from dddesign.structure.services import Service
from dddesign.utils.base_model import create_pydantic_error_instance

from app.purchase_context.domains.entities.order import Order
from app.purchase_context.domains.entities.currency_rate import CurrencyRate
from app.purchase_context.domains.value_objects.money import Money


TARGET_CURRENCY = 'USD'


class ConvertToUSDService(Service):
    order: Order
    currency_rate: CurrencyRate
    
    @model_validator(mode='after')
    def validate_consistency(self):
        if self.currency_rate.to_currency != TARGET_CURRENCY:
            raise create_pydantic_error_instance(
                base_error=ValueError,
                code='invalid_target_currency',
                message=f'Target currency must be {TARGET_CURRENCY}',
            )

        if self.order.total.currency != self.currency_rate.from_currency:
            raise create_pydantic_error_instance(
                base_error=ValueError,
                code='currency_mismatch',
                message='Order currency does not match rate source currency',
            )

        return self

    def handle(self) -> Money:
        return Money(
            amount=self.order.total.amount * self.currency_rate.rate,
            currency=self.currency_rate.to_currency,
        )
```
