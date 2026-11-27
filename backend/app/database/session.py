from collections.abc import Generator
from threading import Lock

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models import Base

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

_schema_ready = False
_schema_lock = Lock()


def ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        try:
            Base.metadata.create_all(bind=engine)
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503,
                detail="PostgreSQL is unavailable. Start the database and retry.",
            ) from exc
        _schema_ready = True


def get_db() -> Generator[Session, None, None]:
    ensure_schema()
    with SessionLocal() as session:
        yield session
