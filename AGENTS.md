# AGENTS Quick Guide

## Agent behavior (read first)

* Prefer small, targeted diffs over large rewrites.
* Before coding, inspect nearby code and follow existing patterns.
* Do not introduce abstractions unless there is a clear need.
* If unclear, make one explicit assumption and proceed.
* Ask a question only if choices are mutually exclusive or unsafe.
* Run the narrowest validation first (focused test/command), then full checks if needed.

---

## What matters first

* Use Docker/Fabric for dev commands; this repo is intended to run inside containers, not host Python.
* Bootstrap env once:
  `cp src/config/init_dot_env src/config/.env`
* Main entrypoint commands run from `src/`:
  `python manage.py <command>`

Common commands:

* `runserver`
* `runworker`
* `runscheduler`
* `shell`
* `makemigrations`
* `migrate`
* `downgrade`

---

## Reliable command shortcuts

* Start API locally:
  `fab run`
  → In upstream config API is exposed on `http://localhost:8000`

* Start background services:

  * `fab worker`
  * `fab scheduler`

* Apply migrations:

  * `fab migrate`
  * DB selectable via `--db postgres|clickhouse`

* Run linters (expected order):

  * `fab linters`
    (ruff fix → format → import-linter → ty → complexipy)

* Run tests:

  * `fab tests`
  * Focused run:
    `fab execute:"pytest <path_or_nodeid>"`

---

## Architecture facts that affect changes

* FastAPI app entrypoint:
  `src/config/entrypoints/fastapi.py` → `config.entrypoints.fastapi:app`

* Global API prefix:
  `/api/v1`

* Probes:
  `/api/v1/probe/*`

* Dramatiq task discovery:
  pattern-based →
  `app.*.infrastructure.ports.tasks`
  → tasks outside this path will NOT load

* Current bounded context:
  `app.probe_context`

* Import rules enforced via:
  `lint-imports.toml`
  → boundaries are NOT optional

---

## DDDesign layering rules (practical)

Core mapping:

* HTTP Port → request/response only
* Application → use-case orchestration
* Domain → business logic & state
* Service → pure domain logic (optional)
* Repository → DB access only
* Adapter → external integrations

### Golden path

Port → Application → Domain Entity / Domain Service → Repository / Adapter

* Application orchestrates the use-case
* Domain owns business rules
* Repository/Adapter perform IO

---

## Layer responsibilities (important)

### Application

* One use-case
* Orchestration only
* No business rules
* Dependencies passed explicitly

### Domain (Entity / ValueObject / DTO)

* Source of truth
* Owns invariants and state transitions

### Service (domain service)

* Pure logic only
* No DB / network / filesystem
* No hidden side effects

### Repository

* Persistence boundary
* Returns domain objects / DTOs
* Never leak ORM models

### Adapter

* External systems (HTTP, Kafka, Redis, etc.)
* No business logic

---

## Design heuristics (use in practice)

* Need DB → Repository
* Need external system → Adapter
* Need orchestration → Application
* Need business rule → Domain
* Need cross-entity pure logic → Service

---

## Important nuance (avoid over-engineering)

* One Application = one use-case

* Multiple repositories in one Application:

  * suspicious, not forbidden
  * justify or consider split
  * do NOT split mechanically if transactional

* Avoid introducing ApplicationFactory unless:

  * runtime strategy selection is required

---

## Domain vs database boundary

* Never treat ORM models as business models

Correct flow:
DB model → Repository → Domain Entity / DTO

* No ORM leakage across layers

---

## Endpoint rule

* HTTP layer calls Application only
* No DB / external calls directly from endpoints

---

## Dependency rule

* Application can depend on:

  * Domain
  * Service
  * Repository
  * Adapter

* Lower layers MUST NOT depend upward

---

## Testing strategy (practical)

* Domain / Service:
  → unit tests (pure logic)

* Application:
  → unit tests with fake repo/adapter (default)
  → integration tests when DB/wiring matters

* Adapter:
  → integration-style tests with mocks/stubs

---

## Anti-patterns to avoid

* Fat Application with business logic
* Services calling DB or network
* SQL inside Application
* Business logic in endpoints
* Returning ORM models outside repository
* “God” repositories
* Anemic domain models (no behavior)

---

## Feature layout

Typical structure:

* `applications/`
* `infrastructure/ports/http/`
* `infrastructure/repositories/`
* `infrastructure/adapters/`
* `domains/{entities,dto,errors,services}`
* `infrastructure/urls.py`

Naming:

* `SomethingApp`
* `SomethingRepository`
* `SomethingService`
* `SomethingDTO`

HTTP routes:

* kebab-case + trailing slash

---

## Change validation before coding

Before implementing:

* Map change to layer(s)
* Check dependency direction
* Compare with existing patterns nearby

If mismatch:
→ fix design BEFORE coding

If unclear:
→ make assumption and proceed

---

## Repo-specific constraints

* Async-first (`async` / `await`)

* `__init__.py`:

  * usually empty
  * exceptions:

    * HTTP routers
    * SQLAlchemy models
    * Dramatiq tasks

* Use `Self` for class constructors

* Use `utc_now()` from `ddutils.datetime_helpers`

* SQLAlchemy models:

  * only primitive types
  * validation lives outside ORM

---

## Quality gates & toolchain

* Python 3.12
* Ruff:

  * single quotes
  * line length 128
* Type checker:

  * `ty` (not mypy)
* Import rules:

  * enforced via `lint-imports.toml`
  * treated as architecture constraint, not style

---

## Final mental model (keep in head)

* Follow existing code first
* Keep changes minimal
* Respect boundaries, but don’t over-engineer
* Domain holds logic, Application orchestrates, infra does IO
* If design feels forced → it probably is
