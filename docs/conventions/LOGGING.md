## Logging

Structured JSON logging with request-scoped context, automatic log enrichment, and Sentry integration.

### Handlers

The project has two logging handlers. Both are initialized via `configure_logging_handlers()` in each entrypoint (`fastapi.py`, `dramatiq.py`, `apscheduler.py`). In `DEBUG=True` mode, handlers are not initialized.

#### stdout (`config.logging.handlers.stdout`)

JSON logging to stdout via `python-json-logger`.

- Format: `%(levelname)s %(message)s %(name)s`
- `CustomJsonFormatter` automatically enriches every log record with `LogProperties` of the current request (request_id, duration, headers.*)
- Logger configuration (levels, suppression of noisy libraries): see `LOG_CONFIG` in `config.logging.handlers.stdout.config`

#### Sentry (`config.logging.handlers.sentry`)

Sends errors and warnings to Sentry.

**Activation conditions:** `SENTRY_DSN` is set and `ENVIRONMENT` != `local`.

- Captures WARNING+ level logs as Sentry events
- `before_send` hook enriches Sentry event tags with `LogProperties` (request_id, headers, duration)
- `DramatiqIntegration` tracks errors in background tasks
- Performance tracing enabled

### Entrypoints

#### FastAPI

```
HTTP Request
  |
  +- LogPropertiesManagerMiddleware        <- context initialization (request_id, headers)
  |    |
  |    +- RequestResponseLoggingMiddleware  <- REQUEST / RESPONSE logging
  |         |
  |         +- Application logic
  |              +- logger.info({...})     <- LogProperties automatically in every log
  |
  +- LogProperties cleared
```

**LogPropertiesManagerMiddleware** (`share.fastapi.middlewares`) — initializes `LogProperties` at the start of an HTTP request, clears them after completion.
- Pure ASGI middleware (not `BaseHTTPMiddleware`) — preserves `asyncio.current_task()` context
- `log_properties_registry` is passed explicitly via constructor

**RequestResponseLoggingMiddleware** (`share.fastapi.middlewares`) — logs incoming requests and outgoing responses.
- `REQUEST` — method, URL, url_mask, body as `request_data` (for POST/PUT/PATCH)
- `RESPONSE` — method, URL, url_mask, status_code, body as `response_data`
- Skips OPTIONS requests
- `request_data` / `response_data` are always objects (the ES field is `flattened`). Body content is logged only for JSON media types (`application/json`, `*+json`): a JSON object as-is, an array as `{"items": [...]}`, a scalar as `{"raw": ...}`. Any other body (HTML, form data, CSV, binary, malformed JSON) is logged as `{"content_type": "<media type>", "size": <bytes>}`
- URL masking: `UrlMaskResolver` (trie-based) converts URLs to masks based on registered FastAPI routes (`/projects/abc-123/campaigns/def-456` -> `/projects/<project_id>/campaigns/<campaign_id>`)
- Body size limited by `MAX_BODY_LOG_SIZE` (default 1 MB). Bodies exceeding the limit are logged as the same `{"content_type", "size"}` object

**Example JSON log (REQUEST):**

```json
{
  "levelname": "INFO",
  "message": "REQUEST POST /api/v1/projects/abc/campaigns/",
  "name": "share.fastapi.middlewares.request_response_logging",
  "http_method": "POST",
  "url_path": "/api/v1/projects/abc/campaigns/",
  "url_mask": "/api/v1/projects/<project_id>/campaigns/",
  "masked_request": "POST /api/v1/projects/<project_id>/campaigns/",
  "log_type": "REQUEST",
  "request_id": "a1b2c3d4e5f6",
  "duration": 0.001,
  "headers.ip_address": "10.0.0.1",
  "headers.domain": "api.example.com"
}
```

**Example JSON log (RESPONSE):**

```json
{
  "levelname": "INFO",
  "message": "RESPONSE POST /api/v1/projects/abc/campaigns/",
  "name": "share.fastapi.middlewares.request_response_logging",
  "http_method": "POST",
  "url_path": "/api/v1/projects/abc/campaigns/",
  "url_mask": "/api/v1/projects/<project_id>/campaigns/",
  "masked_request": "POST /api/v1/projects/<project_id>/campaigns/",
  "log_type": "RESPONSE",
  "status_code": 201,
  "request_id": "a1b2c3d4e5f6",
  "duration": 0.042,
  "headers.ip_address": "10.0.0.1",
  "headers.domain": "api.example.com"
}
```

#### Dramatiq

Task logging is implemented via actor middlewares (`share.dramatiq.actor_middlewares`) — classes extending `BaseActorMiddleware` with a `call_next` pattern. Configured in `BaseDramatiqFacade.actor_middlewares`.

```
Actor execution
  |
  +- LogPropertiesManagerMiddleware  <- context initialization (request_id, duration)
  |    |
  |    +- TaskLoggingMiddleware      <- Started / Finished / Failed logging
  |         |
  |         +- Actor logic
  |              +- logger.info({...})  <- LogProperties automatically in every log
  |
  +- LogProperties cleared
```

**LogPropertiesManagerMiddleware** — initializes `LogProperties` (request_id, duration) for the task lifetime and clears them after. `log_properties_registry` is passed explicitly via constructor.

**TaskLoggingMiddleware** — logs:
- Task start with parameters (collections are excluded from the log)
- Task completion with result
- Errors (except `Retry`)

**Example JSON log (Started):**

```json
{
  "levelname": "INFO",
  "message": "Started task campaign_generation_execute_task",
  "name": "share.dramatiq.actor_middlewares.task_logging",
  "generation_id": "gen-123",
  "project_id": "proj-456",
  "request_id": "b2c3d4e5f6a7",
  "duration": 0.0
}
```

**Example JSON log (Finished):**

```json
{
  "levelname": "INFO",
  "message": "Finished task campaign_generation_execute_task",
  "name": "share.dramatiq.actor_middlewares.task_logging",
  "generation_id": "gen-123",
  "project_id": "proj-456",
  "request_id": "b2c3d4e5f6a7",
  "duration": 1.234
}
```

#### APScheduler

No additional logging components. Only base handlers (stdout + Sentry) are used.

### LogProperties (`config.logging.log_properties`)

Request-scoped properties available from anywhere within a request via `log_properties_registry`:

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Request UUID (auto-generated) |
| `start_time` | `float` | Request start time (not logged) |
| `duration` | `float` | Request duration in seconds (computed) |
| `headers.ip_address` | `str \| None` | From `X-Forwarded-For` header |
| `headers.domain` | `str \| None` | From `Host` header |
| `headers.auth_token` | `str \| None` | Masked token from `Authorization` header |

**Token masking:** JWT tokens are decrypted via `DencryptAccessTokenService`, `secret_key_*` tokens are truncated to the first dot.

**log_properties_registry** — scoped registry bound to the execution (HTTP request, actor run), not to a task: the scope key lives in a `ContextVar`, so coroutines spawned inside the request via `asyncio.gather` / `TaskGroup` log with the same `request_id`. Allows retrieving `LogProperties` of the current request from anywhere:

```python
from config.logging.log_properties import log_properties_registry

log_properties = log_properties_registry.get()
if log_properties:
    request_id = log_properties.request_id
```
