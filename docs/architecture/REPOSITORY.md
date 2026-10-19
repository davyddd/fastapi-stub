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

| Method | Description |
|---|---|
| `get` | Returns one entity by PK |
| `get_by_filters` | Returns one entity matching filters |
| `get_list` | Returns a list of entities |
| `get_map` | Returns a mapping of entities (e.g. `{pk: entity}`) |
| `create` | Creates one entity, accepts entity |
| `update` | Updates one entity, accepts entity |
| `delete` | Deletes one entity by PK |
| `bulk_create` | Creates multiple entities, accepts a collection of entities |
| `bulk_update` | Updates multiple entities, accepts a collection of entities |
| `bulk_delete` | Deletes multiple entities, accepts a collection of PKs |
| `update_by_filters` | Updates entities matching filters |
| `delete_by_filters` | Deletes entities matching filters |
| `exists` | Returns whether any entity matches filters |
| `count` | Returns the number of entities matching filters |

Any other method, private helpers included, fails at class definition. Use `EXTERNAL_ALLOWED_METHODS`, declared as
a field, to allow additional methods beyond this set.

```python
class ProfileRepository(Repository):
    EXTERNAL_ALLOWED_METHODS: set[str] | None = {'upsert'}
```
