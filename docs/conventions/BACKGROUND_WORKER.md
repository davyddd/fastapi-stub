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

Periodic tasks use `@cron` decorator. Task names follow the pattern `<application>_<method>_periodic_task`.

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

**Example:**
```python
from datetime import timedelta

from config.dramatiq import dramatiq_facade_impl


dramatiq_facade_impl.send_task(
    task_name='mailing_send_task',
    delay=timedelta(minutes=5),
    mail_type=MailType.WELCOME,
    email='user@example.com',
    context={'name': 'John'},
)
```

### Deployment

Worker pods are defined in `.helm/values.yaml`. Create a separate worker for each queue.

**Example:**
```yaml
worker:
  - name: email-context  # pod name, use dashes
    queues:
      - "email_context"  # queue names from Python code, use underscores
```