import asyncio
# from logging.config import fileConfig

from sqlalchemy import pool, Engine
from sqlalchemy import Connection, create_engine, pool, schema, text
from sqlalchemy.ext.asyncio import (
    async_engine_from_config,
    create_async_engine,
    AsyncEngine,
    AsyncConnection,
)
from sqlalchemy.sql.schema import MetaData

from alembic import context

# from models import City
from src.settings import getSettings
from src.schema import Base, Schema

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
# config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# ... etc.

target_metadata = Base.metadata
include_schemas = True
compare_type = True
compare_server_default = True

MANAGED_SCHEMA_NAMES = list(Schema)


def includeName(name: str | None, db_obj_type: str, parent_names: dict) -> bool:
    if db_obj_type == "schema":
        return name in MANAGED_SCHEMA_NAMES
    return True


async def ensureSchemas(connection: AsyncConnection) -> None:
    for name in MANAGED_SCHEMA_NAMES:
        await connection.execute(schema.CreateSchema(name, if_not_exists=True))


CONFIGURE_KWARGS: dict = {
    "target_metadata": target_metadata,
    "include_schemas": include_schemas,
    "include_name": includeName,
    "compare_type": compare_type,
    "compare_server_default": compare_server_default,
}


def run_migrations_offline(database_url: str) -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **CONFIGURE_KWARGS,
    )

    with context.begin_transaction():
        for schema in MANAGED_SCHEMA_NAMES:
            context.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        context.run_migrations()


def run_sync_migrations(connection: Connection) -> None:
    context.configure(connection=connection, **CONFIGURE_KWARGS)

    with context.begin_transaction():
        context.run_migrations()


async def run_connectable(connectable: AsyncEngine):
    try:
        async with connectable.connect() as connection:
            await ensureSchemas(connection)
            await connection.commit()

            async with connectable.connect() as connection:
                await connection.run_sync(run_sync_migrations)
    finally:
        await connectable.dispose()


async def run_async_migrations(database_url: str) -> None:
    connectable: AsyncEngine = create_async_engine(
        database_url, poolclass=pool.NullPool
    )

    await run_connectable(connectable)


def run_migrations_online(database_url: str) -> None:
    connectable: AsyncEngine = create_async_engine(
        database_url, poolclass=pool.NullPool
    )

    asyncio.run(run_connectable(connectable))


database_url = getSettings().db.dsn


if context.is_offline_mode():
    run_migrations_offline(database_url)
else:
    run_migrations_online(database_url)
