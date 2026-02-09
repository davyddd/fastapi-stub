## Repository

**Repository** isolates interactions with data storage systems. Introduced in "Domain-Driven Design" by Eric Evans as a subtype of Adapter.
Repository is injected into Application via dependency injection.

**Constraints:**
1. **One Repository per Application** — if an Application uses more than one Repository,
create a subordinate Application for the additional Repository.
2. **One table per Repository** — each Repository typically manages a single table (Entity).
Exception: complex analytics queries that aggregate data from multiple tables.
3. **Returns Domain objects** — Repository should return Entities, not raw dicts or ORM models.

See implementation examples:
- [POSTGRES.md](../databases/POSTGRES.md)
- [CLICKHOUSE.md](../databases/CLICKHOUSE.md)
- [REDIS.md](../databases/REDIS.md)
- [KAFKA.md](../databases/KAFKA.md)

### Allowed Methods

By default, only these methods are allowed for external access:
`{'get', 'get_list', 'create', 'update', 'delete'}`

Use `EXTERNAL_ALLOWED_METHODS` to allow additional methods.

```python
class ProfileRepository(Repository):
    EXTERNAL_ALLOWED_METHODS: set[str] | None = {'get_by_filters'}
```
