from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING

from qdrant_client import QdrantClient, models
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.services.qdrant import get_qdrant_client

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384
COLLECTION_NAME = "jobs"
DEFAULT_BATCH_SIZE = 32


@dataclass
class IndexingSummary:
    total_jobs: int
    successful: int = 0
    failed: int = 0
    upserted: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def _load_embedding_model() -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def _encode_job_texts(
    texts: Sequence[str],
    batch_size: int,
) -> list[list[float]]:
    vectors = _load_embedding_model().encode(
        list(texts),
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_jobs_collection(client: QdrantClient) -> None:
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )
    else:
        collection = client.get_collection(COLLECTION_NAME)
        vectors = collection.config.params.vectors
        if (
            not isinstance(vectors, models.VectorParams)
            or vectors.size != VECTOR_SIZE
            or vectors.distance != models.Distance.COSINE
        ):
            raise ValueError(
                f"Qdrant collection '{COLLECTION_NAME}' must use one "
                f"{VECTOR_SIZE}-dimension cosine vector."
            )

    ensure_jobs_text_index(client)


def ensure_jobs_text_index(client: QdrantClient) -> None:
    collection = client.get_collection(COLLECTION_NAME)
    index = (collection.payload_schema or {}).get("searchable_text")
    if index is not None:
        if index.data_type != models.PayloadSchemaType.TEXT:
            raise ValueError(
                f"Qdrant field '{COLLECTION_NAME}.searchable_text' "
                "must have a text payload index."
            )
        return

    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="searchable_text",
        field_schema=models.TextIndexParams(
            type=models.TextIndexType.TEXT,
            tokenizer=models.TokenizerType.WORD,
            min_token_len=2,
            lowercase=True,
        ),
        wait=True,
    )


def _record_failure(
    summary: IndexingSummary,
    jobs: Sequence[Job],
    phase: str,
    error: Exception,
) -> None:
    summary.failed += len(jobs)
    first_id = jobs[0].id
    last_id = jobs[-1].id
    summary.errors.append(
        f"{phase} failed for job IDs {first_id}-{last_id} "
        f"({type(error).__name__})."
    )


def index_jobs(
    session: Session,
    *,
    client: QdrantClient | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    encode_texts: Callable[[Sequence[str], int], list[list[float]]] | None = None,
) -> IndexingSummary:
    """Upsert jobs into Qdrant, embedding only new or changed searchable text."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least one.")

    jobs = list(session.scalars(select(Job).order_by(Job.id)).all())
    summary = IndexingSummary(total_jobs=len(jobs))
    if not jobs:
        return summary

    qdrant = client or get_qdrant_client()
    try:
        ensure_jobs_collection(qdrant)
    except Exception as exc:
        _record_failure(summary, jobs, "Qdrant collection setup", exc)
        return summary

    encoder = encode_texts or _encode_job_texts
    for offset in range(0, len(jobs), batch_size):
        batch = jobs[offset : offset + batch_size]
        try:
            existing_points = qdrant.retrieve(
                collection_name=COLLECTION_NAME,
                ids=[job.id for job in batch],
                with_payload=["searchable_text_sha256", "embedding_model"],
                with_vectors=False,
            )
        except Exception as exc:
            _record_failure(summary, batch, "Qdrant lookup", exc)
            continue

        existing_hashes = {
            point.id: (
                (point.payload or {}).get("searchable_text_sha256"),
                (point.payload or {}).get("embedding_model"),
            )
            for point in existing_points
        }
        changed_jobs = [
            job
            for job in batch
            if existing_hashes.get(job.id)
            != (_text_hash(job.searchable_text or ""), MODEL_NAME)
        ]
        summary.unchanged += len(batch) - len(changed_jobs)
        if not changed_jobs:
            continue

        try:
            vectors = encoder(
                [job.searchable_text or "" for job in changed_jobs],
                batch_size,
            )
            if len(vectors) != len(changed_jobs) or any(
                len(vector) != VECTOR_SIZE for vector in vectors
            ):
                raise ValueError(
                    f"Encoder must return one {VECTOR_SIZE}-dimension vector per job."
                )
            points = [
                models.PointStruct(
                    id=job.id,
                    vector=vector,
                    payload={
                        "job_id": job.id,
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "employment_type": job.employment_type,
                        "required_skills": job.required_skills or [],
                        "searchable_text": job.searchable_text or "",
                        "searchable_text_sha256": _text_hash(
                            job.searchable_text or ""
                        ),
                        "embedding_model": MODEL_NAME,
                    },
                )
                for job, vector in zip(changed_jobs, vectors, strict=True)
            ]
            qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=True,
            )
        except Exception as exc:
            _record_failure(summary, changed_jobs, "Embedding or Qdrant upsert", exc)
            continue

        summary.upserted += len(changed_jobs)

    summary.successful = summary.total_jobs - summary.failed
    return summary
