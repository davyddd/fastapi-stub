## Raw SQL

For complex queries (joins, aggregations, analytics), use the `SQLBase` component from `ddsql`. The project's
entry point is `SQL` in `config.databases.services.sql`, with the `postgres` and `clickhouse` adapters wired to the
connection factories. See usage examples in [POSTGRES.md](./POSTGRES.md) and [CLICKHOUSE.md](./CLICKHOUSE.md).

### Serialization

Use `serialize_value(...)` in templates. Strings are escaped per dialect, so quotes, backslashes and control
characters cannot break the query; a NUL character raises for Postgres.

**Type conversions:**

| Python Type | PostgreSQL | ClickHouse |
|-------------|------------|------------|
| `None` | `NULL` | `NULL` |
| `bool` | `true`/`false` | `true`/`false` |
| `int`, `float`, `Decimal` | `123`, `45.67` | `123`, `45.67` |
| `str` | `'value'` | `'value'` |
| `UUID` | `'...'::uuid` | `toUUID('...')` |
| `datetime` (naive) | `'...'::timestamp` | `parseDateTime64BestEffort('...', 6)` |
| `datetime` (aware) | `'...+03:00'::timestamptz` | `parseDateTime64BestEffort('...', 6)` |
| `date` | `'...'::date` | `toDate('...')` |
| `list`/`tuple`/`set` | `(item1, item2)` | `(item1, item2)` |

An `Enum` member is serialized by its value, a subclass as its base type (a `ProfileId(UUID)` as a `UUID`).
`bytes`, dicts, `time` and `timedelta` have no representation and raise `NotImplementedError`; an empty collection
renders as `()`, which is not valid after `IN`, so guard it in the template.

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