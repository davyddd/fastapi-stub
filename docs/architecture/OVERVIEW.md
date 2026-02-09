## Overview

The project follows a Domain‑Driven Design (DDD) inspired architecture with a layered structure.

### DDD Principles

1. **Ubiquitous Language** — everyone in the company (sales, marketing, product, developers)
   should use the same terminology. Code naming should mirror business terminology,
   so anyone can understand what happens at higher levels by reading the code.

2. **Business logic isolation** — domain logic must be independent of frameworks.
   Infrastructure layer components help achieve this (with one exception described in Application).

### Layers

Each bounded context is isolated and has the following layers (from outermost to innermost):
1. **Ports** – entry points into the application, such as HTTP endpoints or background workers tasks.
2. **Applications** – orchestrate business logic. It serves as an interaction interface for a specific domain entity,
and it may also implement complex business scenarios (use cases). It may call other applications (leading/following pattern).
3. **Repositories and adapters** – manage communication with external services. 
Each repository corresponds to exactly one database table (except difficult analytics queries and aggregates); 
adapters encapsulate external / internal services.
4. **Services** – pure business logic. They must not depend on applications, repositories or adapters.
5. **Domains** – core building blocks: entities, value objects, aggregates, DTOs, errors, and constants.
Domains represent the ubiquitous language of the system and can be used by any layer.

### Rich Domain Model over Anemic

Prefer implementing business logic through Domain methods rather than keeping Domains as plain data containers.
If Domains are properly decomposed, there will be no cognitive overload when working with them.
Services should only be used for logic that doesn't naturally belong to any single Domain.

### Context structure

```text
<context_name>/
├── applications/
├── services/
├── domains/
│   ├── aggregates/
│   ├── constants/
│   ├── dto/
│   ├── entities/
│   ├── errors/
│   └── value_objects/
├── infrastructure/
│   ├── adapters/
│   │   ├── external/
│   │   └── internal/
│   ├── ports/
│   │   ├── http/
│   │   └── tasks/
│   ├── repositories/
│   └── urls.py
├── tests/
│   ├── applications/
│   ├── services/
│   └── domains/
```

<img src="https://raw.githubusercontent.com/davyddd/wiki/refs/heads/main/media/domain-driven-design/component-interaction-flowchart.jpg" alt="Component Interaction Flowchart" width="600">
Figure 1 — Component Interaction Flowchart