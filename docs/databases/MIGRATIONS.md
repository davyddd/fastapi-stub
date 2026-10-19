## Migrations   

The project uses Alembic for database migrations with separate version histories for each database.

**Databases:**
- `postgres`
- `clickhouse`

**Migration location:** `src/alembic/<database>/versions/` (empty in the stub, kept by a `.gitkeep`)

**Commands** (`--db` defaults to `postgres`):
```bash
./manage.py makemigrations --db <database> --message "Added X"
./manage.py checkmigrations --db <database>
./manage.py mergemigrations --db <database> --message "merge heads"
./manage.py migrate --db <database>
./manage.py downgrade --db <database>
```

`checkmigrations` fails when the migration files do not apply cleanly or do not fully reflect the models. Alembic
can only diff models against a live schema, so the files are replayed into the target database first, and only
when it is completely empty (a CI scratch container); a database with a schema that is not at head is refused,
never upgraded. It is Postgres-only, ClickHouse has no autogenerate. `mergemigrations` creates an empty revision
that joins diverging heads.

**Notes**:
- Each migration should represent one logical change.
- PostgreSQL migrations are auto-generated from `SQLModel` definitions.
- ClickHouse migrations need to be written manually,
because `SQLModel` cannot cover all ClickHouse-specific features (engines, partitions, TTL, etc.).
- ClickHouse migrations run over the native protocol (`clickhouse+native://…:9000`, derived from `CLICKHOUSE_URL`
by `manage.py`); the compose publishes only the HTTP port, so they run from inside the compose network.
- ClickHouse tables must use `ReplicatedMergeTree` engine (or other `Replicated*` variants) 
and include `ON CLUSTER '{cluster}'` in all DDL statements (`CREATE TABLE`, `DROP TABLE`, `ALTER TABLE`). 
This ensures migrations work identically on single-node (local/test) and multi-node (prod) environments.