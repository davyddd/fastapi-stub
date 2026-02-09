## Data Transfer Object

**DTO** is a simple data structure used to transfer data between architectural layers.
DTOs define explicit data contracts between Application, Ports, and Adapters.
The pattern was described by Martin Fowler in "Patterns of Enterprise Application Architecture".

**Constraints:**
1. **Data contracts** — defines clear structures for exchanging data between layers.
2. **Immutability** — DTOs cannot be modified after creation.
3. **No infrastructure dependencies** — if fulfilling a contract requires fetching additional data,
this logic belongs in the Application.

**Example:**
```python
from dddesign.structure.domains.dto import DataTransferObject


class ProfileDTO(DataTransferObject):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
```
