from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.core.config import get_settings
from app.database.session import SessionLocal
from app.services.resumes import recover_stale_resume_extractions

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        with SessionLocal() as session:
            recovered = recover_stale_resume_extractions(session)
    except SQLAlchemyError as exc:
        logger.warning(
            "Resume startup recovery skipped (%s).", type(exc).__name__
        )
    else:
        if recovered:
            logger.warning(
                "Marked %s stale resume extraction(s) retryable at startup.",
                recovered,
            )
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(_, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Database request failed (%s).", type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database request failed. Check PostgreSQL and retry."},
    )
