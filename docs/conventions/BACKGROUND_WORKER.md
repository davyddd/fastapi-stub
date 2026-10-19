## Background workers

Async background worker based on `dramatiq` with Redis broker.

### Task Definition

Tasks are located in `<context>/infrastructure/ports/tasks/`.
Use a context name as a queue name. Task names follow the pattern `<application>_<method>_task`.

**Example:**
```python
from datetime import timedelta

import dramatiq

from ddutils.convertors import convert_timedelta_to_milliseconds


@dramatiq.actor(
    queue_name='email_context',
    priority=0,
    max_retries=20,
    min_backoff=convert_timedelta_to_milliseconds(timedelta(minutes=1)),
    max_backoff=convert_timedelta_to_milliseconds(timedelta(minutes=2)),
    max_age=convert_timedelta_to_milliseconds(timedelta(minutes=5)),
    time_limit=convert_timedelta_to_milliseconds(timedelta(minutes=5)),
)
async def mailing_send_task(mail_type: MailType, email: EmailStr, context: dict):
    await mailing_app_impl.send(mail_type=mail_type, email=email, context=context)
```

### Cron Tasks

Periodic tasks use the `@cron` decorator, placed outside `@dramatiq.actor`. Task names follow the pattern
`<application>_<method>_periodic_task`. The scheduler (`./manage.py runscheduler`) only enqueues the actor on its
crontab, in UTC; the work itself runs on a worker.

**Example:**
```python
import dramatiq

from share.dramatiq.decorators.cron_decorator import cron


@cron('0 6 * * *')  # every day at 06:00
@dramatiq.actor(queue_name='email_context', ...)
async def mailing_collect_dmarc_reports_periodic_task():
    await mailing_app_impl.collect_dmarc_reports()
```

### Facade

Use `dramatiq_facade_impl` to send tasks. 
Since `send_task` connects to Redis, it's recommended to call it from the Adapter layer. 
However, calling directly from the Application layer is also acceptable.

`send_task(task_name, delay=None, *args, **kwargs)`: `delay` is an `int` of milliseconds or a `timedelta`; the
arguments go through a JSON round trip (UUIDs, datetimes and enums arrive as strings, the actor's type hints are
not applied), so pass what the actor can rebuild. `run_task_sync(task_name, *args, **kwargs)` runs the actor in
place with the same serialization, for scripts and tests. Actors are `async def`: `setup_tasks()` wraps every
actor's function with the actor middlewares and `async_to_sync`.

**Example:**
```python
from datetime import timedelta

from config.entrypoints.dramatiq import dramatiq_facade_impl


dramatiq_facade_impl.send_task(
    task_name='mailing_send_task',
    delay=timedelta(minutes=5),
    mail_type=MailType.WELCOME,
    email='user@example.com',
    context={'name': 'John'},
)
```

### Deployment

Run a separate worker per queue (`./manage.py runworker --queues <queue>`), so a slow queue does not starve the
others. How the workers are declared is up to the deployment; in a Helm chart it is one entry per queue:

**Example:**
```yaml
worker:
  - name: email-context  # pod name, use dashes
    queues:
      - "email_context"  # queue names from Python code, use underscores
```