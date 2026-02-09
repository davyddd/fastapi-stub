# Getting Started

## Table of Contents

- [Docker](#docker)
- [Development](#development)
  - [First launch](#first-launch)
  - [Environments](#environments)
  - [Management Commands](#management-commands)
  - [Fabric](#fabric)
  - [Dependency Management](#dependency-management)
  - [Code Analysis](#code-analysis)
  - [Debugging](#debugging)
- [Application](#application)
  - [Architecture](#architecture)
  - [Stack](#stack)
  - [Databases](#databases)
  - [Conventions](#conventions)

## Docker

The project uses two Docker images:
- `Dockerfile-base` — base image with system packages, dependencies and uv
- `Dockerfile` — main image built on top of the base

This separation avoids unnecessary rebuilds caused by system package updates (`apt-get update`),
which would otherwise trigger time-consuming reinstallation of Python packages.

Installation instructions and more details about Docker architecture can be found in [this article](https://github.com/davyddd/wiki/blob/main/articles/docker-and-compose.md).

## Development

### First launch

1. Copy the environment file template (see [Environments](#environments) for details):

    ```bash
    cp src/config/init_dot_env src/config/.env
    ```

2. Run migrations

   ```bash
   fab migrate
   ```

3. Start the web server

    ```bash
    fab run
    ```

### Environments

The project loads environment variables from `src/config/.env`.
This file is listed in `.gitignore`, so it's safe to store secrets there — they won't be committed to version control.
To create the file initially, you can use `src/config/init_dot_env` as a template.

### Management Commands

`./src/manage.py` is a django-like entry-point script for application-specific ops like migrations, server launch etc.

Example:
```shell
# run uvicorn server
./manage.py runserver

# run dramatiq for ALL queues and watch for changes
./manage.py runworker --processes 1 --threads 1 --watch

# migrations
./manage.py makemigrations --message 'Added A for B'
./manage.py migrate
./manage.py downgrade

# launching python repl (ipython or built-in)
./manage.py shell
```

### Fabric

`fabric` provides shortcuts for common Docker-based development commands.

Install `fabric3` (unofficial package) or `fabric<2.0` (official package):

```bash
sudo pip3 install Fabric3
```

or

```bash
sudo pip install "fabric<2.0"
```

Commands:

* `fab base` - build / rebuild the base image (probably will never be needed)
* `fab build` - build / rebuild the main image
* `fab linters` - run available linters (see details in [Code Analysis](#code-analysis))
* `fab run` - run the web application locally
* `fab worker` - run the background worker locally
* `fab scheduler` - run the task scheduler locally
* `fab makemigrations` - create migration files
* `fab migrate` - apply migrations
* `fab shell` - enter shell
* `fab bash` - enter container's bash
* `fab kill` - kill all running docker containers

**Note**: When modifying project dependencies, remember to rebuild the docker image using the `fab build` command.

### Dependency Management

Project dependencies are orchestrated by [uv](https://docs.astral.sh/uv/).

* `uv add <package>` - install a package
* `uv remove <package>` - remove a package
* `uv self update` - update uv version
* `uv lock` - update project lockfile

**Note**: Always specify a version for each dependency — either an exact version
or a version range (e.g., >=1.2.0) — to ensure consistent and predictable builds.

### Code Analysis

Tools used to ensure standardization:

| Tool                                                           | Settings file       | Purpose                       |
|----------------------------------------------------------------|---------------------|-------------------------------|
| [ruff](https://docs.astral.sh/ruff/)                           | `ruff.toml`         | linting and formatting        |
| [ty](https://docs.astral.sh/ty/)                               | `ty.toml`           | type checking                 |
| [importliner](https://import-linter.readthedocs.io/en/stable/) | `lint-imports.toml` | DDD principles, src integrity |

Examples of using code-linting tools:
```shell
# run ruff analyzer
ruff check --config ruff.toml

# run ruff code-formatter
ruff format --check --config ruff.toml

# run ty type checker
ty check --config-file ty.toml

# lint imports
lint-imports --config lint-imports.toml
```

### Debugging

* `ipdb` — use the `breakpoint()` builtin call
* PyCharm Debugger — [setup guide](https://github.com/davyddd/wiki/blob/main/articles/setting-up-pycharm.md)

## Application

### Architecture

The project follows Domain-Driven Design (DDD) principles with a layered structure.
High-level overview and detailed documentation for each component:

- [Overview](docs/architecture/OVERVIEW.md) — DDD principles, layers and project structure
- [Context](docs/architecture/CONTEXT.md) — bounded contexts
- [Application](docs/architecture/APPLICATION.md) — domain logic orchestration and use cases
- [Repository](docs/architecture/REPOSITORY.md) — data storage isolation
- [Adapter](docs/architecture/ADAPTER.md) — external and internal service integration
- [Service](docs/architecture/SERVICE.md) — reusable business logic without infrastructure dependencies
- [Aggregate](docs/architecture/AGGREGATE.md) — collection of related entities as a single unit
- [Entity](docs/architecture/ENTITY.md) — domain objects with unique identity
- [Data Transfer Object](docs/architecture/DATA_TRANSFER_OBJECT.md) — immutable data contracts between layers
- [Value Object](docs/architecture/VALUE_OBJECT.md) — immutable objects defined by properties

### Stack

Application:
- `fastapi` — web framework and automated swagger documentation
- `dramatiq` — async task queue (Redis as broker)
- `apscheduler` — scheduled tasks
- `pydantic` — serialization and data validation
- `alembic` — database migrations
- `sqlmodel`, `sqlalchemy` (core), `psycopg` — Postgres ORM and driver
- `clickhouse-connect`, `clickhouse-sqlalchemy` — ClickHouse HTTP client and SQLAlchemy dialect
- `redis` — Redis client
- `aiokafka` — Kafka client
- `httpx` — HTTP client for external services
- [dddesign](https://github.com/davyddd/dddesign) — DDD building blocks
- [ddutils](https://github.com/davyddd/ddutils) — shared utilities (convertors, object getters)
- [ddsql](https://github.com/davyddd/ddsql) — SQL query builder and database adapters

### Databases

Infrastructure:
- PostgreSQL — primary data storage
- ClickHouse — analytical data storage
- Redis-compatible in-memory DB (Redis, KeyDB, ValKey, Dragonfly, etc.) — temporary data and task broker
- Kafka — event streaming

Details on working with each database:

- [Migrations](docs/databases/MIGRATIONS.md) — Alembic with separate histories per database
- [Postgres](docs/databases/POSTGRES.md) — ORM models, UUID primary keys, timestamp mixins
- [ClickHouse](docs/databases/CLICKHOUSE.md) — table creation via native SQL migrations
- [Raw SQL](docs/databases/RAW_SQL.md) — complex queries using SQLBase and serialization
- [Redis](docs/databases/REDIS.md) — async client for caching and distributed locking
- [Kafka](docs/databases/KAFKA.md) — async message production and consumption

### Conventions

Project conventions and agreements:

- [Naming](docs/conventions/NAMING.md) — class, file and instance naming patterns
- [Imports](docs/conventions/IMPORTS.md) — architectural boundaries and layer contracts
- [Errors](docs/conventions/ERRORS.md) — unified error handling with exception handlers
- [Background Workers](docs/conventions/BACKGROUND_WORKER.md) — Dramatiq tasks, queues and scheduling
