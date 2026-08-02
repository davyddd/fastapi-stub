import importlib
import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from config.settings import settings

from share.sqlmodel.models.base import BaseSQLModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name:
    fileConfig(config.config_file_name)  # type: ignore


target_metadata = BaseSQLModel.metadata


def load_models():
    root_dir = settings.ROOT_DIR
    app_dir = os.path.join(root_dir, 'app')

    for context_name in os.listdir(app_dir):
        models_init_file = os.path.join(app_dir, context_name, 'infrastructure', 'models', '__init__.py')
        if os.path.isfile(models_init_file):
            module_name = f'app.{context_name}.infrastructure.models'
            importlib.import_module(module_name)


load_models()

# Child partitions of partitioned tables (e.g. sticky_email_settings_model_y2026m07) have no
# SQLModel of their own — they are created and dropped by a periodic task. Without this filter
# autogenerate would reflect them as unknown tables and emit drop_table for each.
PARTITION_TABLE_RE = re.compile(r'.+_y\d{4}m\d{2}$')


def include_object(obj, name, type_, reflected, compare_to) -> bool:  # noqa: ARG001
    if type_ == 'table' and reflected and compare_to is None and PARTITION_TABLE_RE.match(name or ''):
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=config.get_main_option('sqlalchemy.url'),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)
    connectable = engine_from_config(configuration, prefix='sqlalchemy.', poolclass=pool.NullPool)  # type: ignore

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
