
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()

    if settings.database_backend == "sqlite":
        if not settings.database_url.startswith("sqlite:"):
            raise RuntimeError(
                "SQLite mode requires a sqlite: DATABASE_URL."
            )

        engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    # Cloud SQL support: activated only when configured.
    if not all([
        settings.cloud_sql_instance,
        settings.db_user,
        settings.db_password,
        settings.db_name,
    ]):
        raise RuntimeError(
            "Cloud SQL configuration is incomplete."
        )

    from google.cloud.sql.connector import Connector, IPTypes

    connector = Connector(refresh_strategy="LAZY")

 
    ip_mode = settings.cloud_sql_ip_type.strip().upper()

    if ip_mode not in {"PUBLIC", "PRIVATE"}:
        raise RuntimeError(
            "CLOUD_SQL_IP_TYPE must be PUBLIC or PRIVATE."
        )

    ip_type = (
        IPTypes.PUBLIC
        if ip_mode == "PUBLIC"
        else IPTypes.PRIVATE
    )


    def connect():
        return connector.connect(
            settings.cloud_sql_instance,
            "pg8000",
            user=settings.db_user,
            password=settings.db_password,
            db=settings.db_name,
            ip_type=ip_type,
        )

 
    return create_engine(
        "postgresql+pg8000://",
        creator=connect,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=1800,
    )



@lru_cache
def get_session_factory():
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def get_db() -> Iterator[Session]:
    session = get_session_factory()()

    try:
        yield session
    finally:
        session.close()
