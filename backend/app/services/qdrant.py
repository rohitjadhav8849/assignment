from functools import lru_cache

from qdrant_client import QdrantClient

from app.core.config import get_settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    api_key = (
        settings.qdrant_api_key.get_secret_value()
        if settings.qdrant_api_key
        else None
    )
    return QdrantClient(url=settings.qdrant_url, api_key=api_key or None)
