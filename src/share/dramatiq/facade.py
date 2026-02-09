import glob
import importlib
import os
from abc import ABC
from dataclasses import dataclass
from datetime import timedelta
from json import dumps, loads
from typing import Any, ClassVar, Generator

from dramatiq import Broker, Message, get_broker
from dramatiq.asyncio import async_to_sync

from ddutils.convertors import convert_timedelta_to_milliseconds

from share.dramatiq.decorators import close_db_connections_decorator
from share.dramatiq.decorators.cron_decorator import CRONTAB_ATTRIBUTE


@dataclass
class JsonMessageArgsSerializer:
    args: tuple[Any, ...] | None = None
    kwargs: dict[str, Any] | None = None

    @property
    def serialized_args(self) -> tuple[Any, ...]:
        return tuple(loads(dumps(self.args))) if self.args else ()

    @property
    def serialized_kwargs(self) -> dict[str, Any]:
        return loads(dumps(self.kwargs)) if self.kwargs else {}


class BaseDramatiqFacade(ABC):
    """
    Base facade for discovering and interacting with Dramatiq tasks.

    This facade is broker-independent and uses `dramatiq.get_broker()` to get
    the currently configured broker. Make sure the broker is initialized before
    using this facade.

    Class Attributes:
        base_dir: Base directory for scanning task modules.
        module_pattern: Module pattern with optional * wildcards.
            Examples:
                - 'app.*.infrastructure.ports.tasks' (single wildcard)
                - 'app.*.*.tasks' (multiple wildcards)
                - 'app.context.tasks' (no wildcards)

    Example:
        # config/dramatiq.py
        from share.dramatiq.facade import BaseDramatiqFacade
        from config.settings import settings

        class DramatiqFacade(BaseDramatiqFacade):
            base_dir = settings.ROOT_DIR
            module_pattern = 'app.*.infrastructure.ports.tasks'

        dramatiq_facade_impl = DramatiqFacade()
        dramatiq_facade_impl.setup_tasks()

        # Usage in other modules
        from config.dramatiq import dramatiq_facade_impl

        dramatiq_facade_impl.send_task(task_name='my_task', arg1='value')
    """

    base_dir: ClassVar[str]
    module_pattern: ClassVar[str]

    _is_setup: bool = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if not getattr(cls, 'base_dir', None):
            raise ValueError('`base_dir` class attribute must be set')

        if not getattr(cls, 'module_pattern', None):
            raise ValueError('`module_pattern` class attribute must be set')

    def get_tasks_modules(self) -> Generator[str, None, None]:
        """
        Scan directories and yield task module paths based on the pattern.

        Supports glob wildcards (*) in the pattern.
        Example: 'app.*.infrastructure.ports.tasks' or 'app.context.tasks'

        Yields:
            Module paths match the pattern.
        """
        pattern_path = self.module_pattern.replace('.', os.sep)
        search_pattern = os.path.join(self.base_dir, pattern_path, '__init__.py')

        for init_file in glob.glob(search_pattern):
            module_dir = os.path.dirname(init_file)
            rel_path = os.path.relpath(module_dir, self.base_dir)
            module_name = rel_path.replace(os.sep, '.')
            yield module_name

    def setup_tasks(self):
        """
        Discover, import, and prepare all task modules for execution.

        This method:
        1. Scans directories for task modules based on the configured pattern
        2. Imports all found modules to register actors
        3. Wraps actors with async_to_sync and db connection closer
        """
        if self._is_setup:
            return

        for module_name in self.get_tasks_modules():
            importlib.import_module(module_name)

        for actor in get_broker().actors.values():
            actor.fn = async_to_sync(close_db_connections_decorator(actor.fn.__wrapped__))  # ty: ignore[unresolved-attribute]

        self._is_setup = True

    def send_task(self, task_name: str, delay: int | timedelta | None = None, *args: Any, **kwargs: Any) -> None:
        """
        Send a task to the broker queue.

        Args:
            task_name: Name of the registered actor/task.
            delay: Optional delay before task execution (int in ms or timedelta).
            *args: Positional arguments for the task.
            **kwargs: Keyword arguments for the task.
        """
        actor = self.broker.get_actor(task_name)

        if isinstance(delay, timedelta):
            delay = convert_timedelta_to_milliseconds(delay)

        if not delay:
            delay = None

        options = {}
        if actor.options:
            options.update(actor.options)

        if actor.priority:
            options['priority'] = actor.priority

        serializer = JsonMessageArgsSerializer(args=args, kwargs=kwargs)

        message: Message = Message(
            queue_name=actor.queue_name,
            actor_name=task_name,
            args=serializer.serialized_args,
            kwargs=serializer.serialized_kwargs,
            options=options,
        )
        self.broker.enqueue(message=message, delay=delay)

    def run_task_sync(self, task_name: str, *args: Any, **kwargs: Any) -> Any:
        """
        Run a task synchronously without sending to the broker.

        Args:
            task_name: Name of the registered actor/task.
            *args: Positional arguments for the task.
            **kwargs: Keyword arguments for the task.

        Returns:
            Task result.
        """
        actor = self.broker.get_actor(task_name)

        serializer = JsonMessageArgsSerializer(args=args, kwargs=kwargs)

        return actor(*serializer.serialized_args, **serializer.serialized_kwargs)

    def get_cron_jobs(self) -> Generator[tuple[str, str, str], None, None]:
        """
        Yield cron job configurations for actors with @cron decorator.

        Yields:
            Tuples of (job_path, crontab, job_name) for each cron actor.
        """
        for actor in self.broker.actors.values():
            if hasattr(actor, CRONTAB_ATTRIBUTE):
                crontab = getattr(actor, CRONTAB_ATTRIBUTE)
                module_path = actor.fn.__module__
                func_name = actor.fn.__name__  # ty: ignore[unresolved-attribute]

                yield (
                    f'{module_path}:{func_name}.send',  # job_path
                    crontab,  # crontab expression
                    f'{module_path}.{func_name}',  # job_name
                )

    @property
    def broker(self) -> Broker:
        if not self._is_setup:
            raise RuntimeError('Tasks have not been set up. Call setup_tasks() first.')

        return get_broker()
