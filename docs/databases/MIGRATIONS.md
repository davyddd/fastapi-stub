## Migrations   

The project uses Alembic for database migrations with separate version histories for each database.

**Databases:**
- `postgres`
- `clickhouse`

**Migration location:** `src/alembic/<database>/versions/`

**Commands:**
```bash
./manage.py makemigrations --db <database> --message "Added X"
./manage.py migrate --db <database>
./manage.py downgrade --db <database>
```

**Notes**:
- Each migration should represent one logical change.
- PostgreSQL migrations are auto-generated from `SQLModel` definitions.
- ClickHouse migrations need to be written manually, 
because `SQLModel` cannot cover all ClickHouse-specific features (engines, partitions, TTL, etc.).