import code
import multiprocessing
import os
import re

import typer
import uvicorn

from dddesign.structure.domains.constants import BaseEnum

from config.logging.config import LOG_CONFIG
from config.settings import settings

from alembic import command
from alembic.config import Config

cli = typer.Typer()
CPU_COUNT = multiprocessing.cpu_count()


class Database(str, BaseEnum):
    POSTGRES = 'postgres'
    CLICKHOUSE = 'clickhouse'

    @property
    def url(self) -> str:
        clickhouse_url = re.sub(r'^.*?://', 'clickhouse+native://', str(settings.CLICKHOUSE_URL))
        return {self.POSTGRES: str(settings.POSTGRES_URL), self.CLICKHOUSE: clickhouse_url}[self]

    @property
    def section(self) -> str:
        return f'db.{self.value}'

    @property
    def autogenerate(self) -> bool:
        return {self.POSTGRES: True, self.CLICKHOUSE: False}[self]


@cli.command()
def shell():
    try:
        from IPython import start_ipython

        start_ipython(argv=[], user_ns={'settings': settings})
    except ImportError:
        code.interact(local={'settings': settings})


@cli.command()
def runserver(host: str = '0.0.0.0', port: int = 8000) -> None:
    config = {
        'app': 'config.entrypoints.fastapi:app',
        'host': host,
        'port': port,
        'reload': settings.DEBUG,
        'proxy_headers': True,
    }
    if not settings.DEBUG:
        config['log_config'] = LOG_CONFIG

    uvicorn.run(**config)  # type: ignore[arg-type]


@cli.command()
def runworker(
    processes: int = CPU_COUNT, threads: int = CPU_COUNT, queues: list[str] | None = None, watch: bool = False
) -> None:
    args = ['dramatiq', 'config.entrypoints.dramatiq', '--path', '.', '--processes', str(processes), '--threads', str(threads)]

    if queues:
        args.extend(['--queues', *queues])
    if watch:
        args.extend(['--watch', settings.ROOT_DIR])

    os.execvp('/usr/local/bin/dramatiq', args)


@cli.command()
def runscheduler():
    from config.entrypoints.apscheduler import scheduler

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


def get_alembic_config(db: Database) -> Config:
    config = Config(os.path.join(settings.ROOT_DIR, 'alembic.ini'))
    config.config_ini_section = db.section
    config.set_main_option('sqlalchemy.url', str(db.url))
    return config


@cli.command()
def makemigrations(message: str = 'Auto-generated migration', db: str = Database.POSTGRES) -> None:
    db = Database(db)
    config = get_alembic_config(db=db)
    command.revision(config, message=message, autogenerate=db.autogenerate)


@cli.command()
def migrate(revision: str = 'head', *, offline: bool = False, db: str = Database.POSTGRES) -> None:
    db = Database(db)
    config = get_alembic_config(db=db)
    command.upgrade(config, revision, offline)


@cli.command()
def downgrade(revision: str = '-1', *, offline: bool = False, db: str = Database.POSTGRES) -> None:
    db = Database(db)
    config = get_alembic_config(db=db)
    command.downgrade(config, revision, offline)


if __name__ == '__main__':
    cli()
