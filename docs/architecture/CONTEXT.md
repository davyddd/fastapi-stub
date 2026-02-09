## Context

In simplified terms, a **Context** is a microservice. Group related domain entities and their operations.

### Cross-Context Communication

- **Ideal:** No direct dependencies between contexts. All interactions via HTTP, gRPC, or message bus.
- **Pragmatic:** Initially, use Internal Adapters to call other contexts directly.
Later, replace with network/message-based communication without changing the interface.

### Subordinate Context

In rare cases (typically analytics), a subordinate context may implement its own Application, Repository, and Domain
to query data from multiple tables. But it is worth considering the following:
1. **Read-only in subordinate context** — only SELECT operations allowed in Repository.
All CUD (Create, Update, Delete) must happen in the owning context.
2. **Database-level coupling** — be aware that this creates a dependency at the database level.
