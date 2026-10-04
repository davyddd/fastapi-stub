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

### Choosing the database

`Adapter.using(...)` lets the repository decide right before executing which database a query goes to;
without it the connection factory's default applies:

```python
result = await SQL(query).with_params(...).postgres.execute()                               # PostgresConnectionAlias.PRIMARY
result = await SQL(query).with_params(...).postgres.using(PostgresConnectionAlias.REPLICA).execute()
```

### File Templates

Instead of inline `text`, pass `path` (a `Path`) to a file-based template. The file is checked when the `Query`
is created, so a wrong path fails on import. `{% include %}` inside the template resolves relative to the file.

```python
from pathlib import Path

SQL_TEMPLATES_DIR = Path(__file__).parent / 'templates' / 'sql'

query = Query(
    model=User,
    path=SQL_TEMPLATES_DIR / 'users' / 'get_by_id.sql',
)
```