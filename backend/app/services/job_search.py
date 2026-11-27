from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from qdrant_client import QdrantClient

from app.services.job_embeddings import (
    COLLECTION_NAME,
    VECTOR_SIZE,
    _encode_job_texts,
    ensure_jobs_text_index,
)
from app.services.qdrant import get_qdrant_client

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_BM25_K1 = 1.5
_BM25_B = 0.75
_SCROLL_BATCH_SIZE = 256


@dataclass(frozen=True)
class BM25SearchResult:
    job_id: int
    title: str
    company: str
    score: float


@dataclass(frozen=True)
class SemanticSearchResult:
    job_id: int
    title: str
    company: str
    similarity_score: float


@dataclass(frozen=True)
class HybridSearchResult:
    job_id: int
    title: str
    company: str
    rrf_score: float


def _validate_search_inputs(query: str, top_k: int) -> None:
    if not isinstance(query, str):
        raise TypeError("query must be a string.")
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise TypeError("top_k must be an integer.")
    if top_k < 1:
        raise ValueError("top_k must be at least one.")


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN.findall(text.casefold())
        if len(token) >= 2
    ]


def search_jobs_bm25(
    query: str,
    top_k: int = 10,
    *,
    client: QdrantClient | None = None,
) -> list[BM25SearchResult]:
    """Rank jobs in Qdrant with BM25 over their searchable_text payloads."""
    _validate_search_inputs(query, top_k)

    query_terms = set(_tokens(query))
    if not query_terms:
        return []

    qdrant = client or get_qdrant_client()
    ensure_jobs_text_index(qdrant)

    documents: list[tuple[int, str, str, str, list[str]]] = []
    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            limit=_SCROLL_BATCH_SIZE,
            offset=offset,
            with_payload=["job_id", "title", "company", "searchable_text"],
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            job_id = payload.get("job_id", point.id)
            text = payload.get("searchable_text")
            if (
                isinstance(job_id, bool)
                or not isinstance(job_id, int)
                or not isinstance(text, str)
                or not text.strip()
            ):
                continue
            documents.append(
                (
                    job_id,
                    payload.get("title") or "",
                    payload.get("company") or "",
                    text,
                    _tokens(text),
                )
            )
        if offset is None:
            break

    if not documents:
        return []

    document_frequencies = Counter(
        term
        for _, _, _, _, terms in documents
        for term in set(terms)
    )
    document_count = len(documents)
    average_length = (
        sum(len(document[4]) for document in documents) / document_count
    )
    if average_length == 0:
        return []

    results: list[BM25SearchResult] = []
    for job_id, title, company, _, terms in documents:
        frequencies = Counter(terms)
        length = len(terms)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            frequency_in_corpus = document_frequencies[term]
            inverse_document_frequency = math.log(
                1
                + (document_count - frequency_in_corpus + 0.5)
                / (frequency_in_corpus + 0.5)
            )
            denominator = frequency + _BM25_K1 * (
                1 - _BM25_B + _BM25_B * length / average_length
            )
            score += (
                inverse_document_frequency
                * frequency
                * (_BM25_K1 + 1)
                / denominator
            )
        if score > 0:
            results.append(
                BM25SearchResult(
                    job_id=job_id,
                    title=title,
                    company=company,
                    score=score,
                )
            )

    results.sort(key=lambda result: (-result.score, result.job_id))
    return results[:top_k]


def search_jobs_semantic(
    query: str,
    top_k: int = 10,
    *,
    client: QdrantClient | None = None,
) -> list[SemanticSearchResult]:
    """Search the existing job vectors by cosine similarity to a text query."""
    _validate_search_inputs(query, top_k)
    if not query.strip():
        return []

    query_vectors = _encode_job_texts([query], batch_size=1)
    if len(query_vectors) != 1 or len(query_vectors[0]) != VECTOR_SIZE:
        raise ValueError(
            f"Query encoder must return one {VECTOR_SIZE}-dimension vector."
        )

    qdrant = client or get_qdrant_client()
    response = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vectors[0],
        limit=top_k,
        with_payload=["job_id", "title", "company"],
        with_vectors=False,
    )

    results: list[SemanticSearchResult] = []
    for point in response.points:
        payload = point.payload or {}
        job_id = payload.get("job_id", point.id)
        if (
            isinstance(job_id, bool)
            or not isinstance(job_id, int)
            or point.score is None
        ):
            continue
        results.append(
            SemanticSearchResult(
                job_id=job_id,
                title=payload.get("title") or "",
                company=payload.get("company") or "",
                similarity_score=float(point.score),
            )
        )

    results.sort(key=lambda result: (-result.similarity_score, result.job_id))
    return results


def search_jobs_hybrid(
    query: str,
    top_k: int = 10,
) -> list[HybridSearchResult]:
    """Combine BM25 and semantic rankings using Reciprocal Rank Fusion."""
    _validate_search_inputs(query, top_k)
    if not query.strip():
        return []

    ranked_results = (
        search_jobs_bm25(query, top_k=top_k),
        search_jobs_semantic(query, top_k=top_k),
    )
    scores: dict[int, float] = {}
    metadata: dict[int, tuple[str, str]] = {}

    for results in ranked_results:
        seen_job_ids: set[int] = set()
        for rank, result in enumerate(results, start=1):
            if result.job_id in seen_job_ids:
                continue
            seen_job_ids.add(result.job_id)
            scores[result.job_id] = scores.get(result.job_id, 0.0) + (
                1 / (60 + rank)
            )
            metadata.setdefault(result.job_id, (result.title, result.company))

    combined = [
        HybridSearchResult(
            job_id=job_id,
            title=metadata[job_id][0],
            company=metadata[job_id][1],
            rrf_score=score,
        )
        for job_id, score in scores.items()
    ]
    combined.sort(key=lambda result: (-result.rrf_score, result.job_id))
    return combined[:top_k]
