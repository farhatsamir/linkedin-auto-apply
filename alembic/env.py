import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config # type: ignore
from sqlalchemy import pool # type: ignore

from alembic import context

# ── Add project root to Python path ───────────────────────────────────────────
# This allows Alembic to import app modules correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Import your application's Base and all models ─────────────────────────────
# Every model must be imported here so Alembic can detect the schema
from app.database.database import Base
from app.models.user import User
from app.models.settings import Settings
from app.models.application import Application
from app.models.logs import Log
from app.models.linkedin_session import LinkedInSession
from app.models.auto_apply_run import AutoApplyRun

# ── Alembic config ─────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the static alembic.ini URL with the app's actual configured DB URL.
# This ensures migrations always target the same database the app connects to,
# regardless of environment (local Windows, Docker, or production).
from app.core.config import settings
config.set_main_option("sqlalchemy.url", settings.database_url)

# Use our Base's metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()