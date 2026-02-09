## Raw SQL

For complex queries (joins, aggregations, analytics), use the `SQLBase` component from `ddsql`.
See usage examples in [POSTGRES.md](./POSTGRES.md) and [CLICKHOUSE.md](./CLICKHOUSE.md).

### Serialization

Use `serialize_value(...)` in templates. 

**Type conversions:**

| Python Type | PostgreSQL | ClickHouse |
|-------------|------------|------------|
| `None` | `NULL` | `NULL` |
| `bool` | `true`/`false` | `true`/`false` |
| `int`, `float` | `123`, `45.67` | `123`, `45.67` |
| `str` | `'value'` | `'value'` |
| `UUID` | `'...'::uuid` | `toUUID('...')` |
| `datetime` | `'...'::timestamp` | `parseDateTimeBestEffort('...')` |
| `date` | `'...'::date` | `toDate('...')` |
| `list`/`tuple` | `(item1, item2)` | `(item1, item2)` |

### File Templates

Instead of inline `text`, use `path` for file-based templates.
Set `SQL_TEMPLATES_DIR` environment variable to the templates directory.

```python
query = Query(
    model=User,
    path='users/get_by_id.sql'
)
```