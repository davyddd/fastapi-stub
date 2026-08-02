#!/usr/bin/env python3

import asyncio
import code
import multiprocessing
import os
import re

import typer
import uvicorn
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from sqlalchemy import create_engine, inspect

from dddesign.structure.domains.constants import BaseEnum

from config.settings import settings

from alembic import command

cli = typer.Typer()
CPU_COUNT = multiprocessing.cpu_count()


class Database(str, BaseEnum):
    POSTGRES = 'postgres'
    CLICKHOUSE = 'clickhouse'

    @property
    def url(self) -> str:
        clickhouse_url = re.sub(r'^.*?://', 'clickhouse+native://', str(settings.CLICKHOUSE_URL))
        clickhouse_url = clickhouse_url.replace(':8123/', ':9000/')
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
    uvicorn.run(app='config.entrypoints.fastapi:app', host=host, port=port, reload=settings.DEBUG, proxy_headers=True)


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
def checkmigrations(db: str = Database.POSTGRES) -> None:
    """Fail if migration files don't apply cleanly or don't fully reflect the models.

    Alembic autogenerate can only diff models against a live schema (it has no
    Django-style in-memory replay of migration files), so the files under test
    are first replayed into the target database — but only if it is completely
    empty (a CI scratch container). A database with any existing schema that is
    not at head is refused, never upgraded.
    """
    db = Database(db)
    if not db.autogenerate:
        typer.echo(f'Database {db.value!r} does not support autogenerate, nothing to check', err=True)
        raise typer.Exit(code=2)

    config = get_alembic_config(db=db)
    script_heads = set(ScriptDirectory.from_config(config).get_heads())

    engine = create_engine(db.url)
    with engine.connect() as connection:
        current_heads = set(MigrationContext.configure(connection).get_current_heads())
        is_empty = not inspect(connection).get_table_names()
    engine.dispose()

    try:
        if current_heads != script_heads:
            if not is_empty:
                typer.echo(
                    f'Refusing to check: database has existing schema but is not at head '
                    f'(current={sorted(current_heads)}, head={sorted(script_heads)}). '
                    f'Point checkmigrations at an empty scratch database.',
                    err=True,
                )
                raise typer.Exit(code=2)
            command.upgrade(config, 'head')
        command.check(config)
    except CommandError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error


@cli.command()
def mergemigrations(revisions: str = '', message: str = 'merge heads', db: str = Database.POSTGRES) -> None:
    """Create an empty merge revision that joins diverging alembic heads.

    `revisions` is an optional comma-separated list of revision IDs; default merges all current heads.
    """
    db = Database(db)
    config = get_alembic_config(db=db)
    target: str | list[str] = [r.strip() for r in revisions.split(',') if r.strip()] if revisions else 'heads'
    command.merge(config, target, message=message)


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
