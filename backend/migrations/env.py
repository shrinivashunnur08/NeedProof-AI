
from logging.config import fileConfig

from alembic import context

from app.db.models import Base
from app.db.session import get_engine


config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


if context.is_offline_mode():
    raise RuntimeError(
        "NeedProof migrations require "
        "an active database connection."
    )


with get_engine().connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=(
            connection.dialect.name == "sqlite"
        ),
    )

    with context.begin_transaction():
        context.run_migrations()
