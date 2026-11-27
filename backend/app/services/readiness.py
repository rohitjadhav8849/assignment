import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database.session import engine
from app.services.qdrant import get_qdrant_client

logger = logging.getLogger(__name__)


def check_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except (SQLAlchemyError, OSError):
        logger.warning("PostgreSQL readiness check failed.")
        return False


def check_qdrant() -> bool:
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception as exc:
        logger.warning("Qdrant readiness check failed (%s).", type(exc).__name__)
        return False
