# Development Rules

## Workflow

1. Receive task → ask clarifying questions
2. Create specification with iterations → approve
3. Implement iteratively (300-500 lines per iteration)

## Commands

Service commands are defined in `src/manage.py` (runserver, runworker, runscheduler, shell, migrate, makemigrations, downgrade).

**IMPORTANT:** The project runs entirely in Docker. All commands must be executed inside the application container, not on the host machine. See `fabfile.py` for container management commands.

## Critical Rules

- **Async-first**: always write asynchronous code (async/await)
- **Application**: max 1 Repository, can call other Applications
- **Repository**: 1 table = 1 Repository
- **Service**: no dependencies on App/Repo/Adapter, single `handle` method
- **Contexts**: independent, no cross-imports (except via Adapters)
- **`__init__.py`**: always create in modules, but keep empty. Exceptions: Dramatiq tasks, SQLAlchemy models, HTTP routers in `ports/http/` (need explicit exports)
- **Don't create empty modules**: only create directories/modules when they contain actual code. Don't pre-create empty structures "for future use"
- **`@classmethod` return type**: always use `Self` (from `typing`) as return type for classmethods that return an instance of the class
- **SQLAlchemy models**: use simple types (`str`, `int`, `bool`, etc.) for columns, not enums or complex types. All validation is done at the code level (entities, services)

## Documentation

**IMPORTANT:** When implementing any module (Application, Adapter, Repository, etc.), always read the corresponding documentation first and follow the conventions described there.

**Architecture:**
- `docs/architecture/OVERVIEW.md`
- `docs/architecture/CONTEXT.md`
- `docs/architecture/APPLICATION.md`
- `docs/architecture/REPOSITORY.md`
- `docs/architecture/ADAPTER.md`
- `docs/architecture/SERVICE.md`
- `docs/architecture/AGGREGATE.md`
- `docs/architecture/ENTITY.md`
- `docs/architecture/DATA_TRANSFER_OBJECT.md`
- `docs/architecture/VALUE_OBJECT.md`

**Databases:**
- `docs/databases/POSTGRES.md`
- `docs/databases/CLICKHOUSE.md`
- `docs/databases/REDIS.md`
- `docs/databases/KAFKA.md`
- `docs/databases/MIGRATIONS.md`
- `docs/databases/RAW_SQL.md`

**Conventions:**
- `docs/conventions/NAMING.md`
- `docs/conventions/ERRORS.md`
- `docs/conventions/IMPORTS.md`
- `docs/conventions/BACKGROUND_WORKER.md`
