## Imports

Import rules enforced by `lint-imports` to ensure architectural boundaries.

**Constraints:**

- **Context independence** — contexts must not import from each other. Exception: `**.infrastructure.**` can import from other contexts.
- **Domain layer purity** — business logic must not depend on infrastructure libraries (`fastapi`, `dramatiq`, `httpx`, the database drivers, etc.). Exception: `**.infrastructure.**` can use these libraries. `ddkafka` and `ddredis` are deliberately not forbidden: an application dedicated to consuming a topic runs `KafkaConsumerMaker` with `RedisLock` itself (see [KAFKA.md](../databases/KAFKA.md)).
- **Layers contract** — lower layers must not know about upper layers.

### Layers

```text
infrastructure.ports        (top)
        ↓
applications
        ↓
infrastructure.repositories | infrastructure.adapters
        ↓
services
        ↓
domains                     (bottom)
```

### Configuration

Every time a new bounded context is introduced, update `lint-imports.toml`.

**Example:**
```toml
[[tool.importlinter.contracts]]
name = "Context independence (contexts must not import from each other)"
type = "independence"
modules = [
    # ... other contexts ...
    "app.new_context",
]
ignore_imports = [
    "**.infrastructure.** -> **",
]

[[tool.importlinter.contracts]]
name = "Domain layer purity (domain must not import from infrastructure libraries)"
type = "forbidden"
source_modules = [
    # ... other contexts ...
    "app.new_context",
]

[[tool.importlinter.contracts]]
name = "Layers contract"
type = "layers"
containers = [
    # ... other contexts ...
    "app.new_context",
]
```