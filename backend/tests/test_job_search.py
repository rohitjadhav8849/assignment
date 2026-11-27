import pytest
from qdrant_client import QdrantClient, models

from app.services.job_embeddings import (
    COLLECTION_NAME,
    VECTOR_SIZE,
    ensure_jobs_collection,
)
from app.services import job_search
from app.services.job_search import (
    BM25SearchResult,
    SemanticSearchResult,
    search_jobs_bm25,
    search_jobs_hybrid,
    search_jobs_semantic,
)


@pytest.mark.filterwarnings(
    "ignore:Payload indexes have no effect in the local Qdrant:UserWarning"
)
def test_bm25_search_ranks_payload_text_and_preserves_dense_vectors() -> None:
    client = QdrantClient(":memory:")
    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=1,
                    vector=[1.0] + [0.0] * (VECTOR_SIZE - 1),
                    payload={
                        "job_id": 1,
                        "title": "Python Platform Engineer",
                        "company": "Northwind",
                        "searchable_text": "Python Python APIs PostgreSQL",
                    },
                ),
                models.PointStruct(
                    id=2,
                    vector=[0.0, 1.0] + [0.0] * (VECTOR_SIZE - 2),
                    payload={
                        "job_id": 2,
                        "title": "Python Developer",
                        "company": "Contoso",
                        "searchable_text": "Python APIs",
                    },
                ),
                models.PointStruct(
                    id=3,
                    vector=[0.0, 0.0, 1.0] + [0.0] * (VECTOR_SIZE - 3),
                    payload={
                        "job_id": 3,
                        "title": "Rust Engineer",
                        "company": "Fabrikam",
                        "searchable_text": "Rust systems programming",
                    },
                ),
            ],
            wait=True,
        )

        ensure_jobs_collection(client)
        results = search_jobs_bm25("python", top_k=2, client=client)

        collection = client.get_collection(COLLECTION_NAME)
        assert collection.config.params.vectors.size == VECTOR_SIZE
        assert collection.config.params.vectors.distance == models.Distance.COSINE
        assert [result.job_id for result in results] == [1, 2]
        assert results[0].title == "Python Platform Engineer"
        assert results[0].company == "Northwind"
        assert results[0].score > results[1].score
        assert client.count(COLLECTION_NAME, exact=True).count == 3
        point = client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[1],
            with_payload=True,
            with_vectors=True,
        )[0]
        assert point.payload["searchable_text"] == (
            "Python Python APIs PostgreSQL"
        )
        assert len(point.vector) == VECTOR_SIZE

        assert search_jobs_bm25("   ", client=client) == []
        assert search_jobs_bm25("!!!", client=client) == []
        with pytest.raises(ValueError, match="at least one"):
            search_jobs_bm25("python", top_k=0, client=client)
        with pytest.raises(TypeError, match="query must be a string"):
            search_jobs_bm25(None, client=client)
    finally:
        client.close()


def test_semantic_search_encodes_query_and_returns_cosine_order(monkeypatch) -> None:
    client = QdrantClient(":memory:")
    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=11,
                    vector=[1.0] + [0.0] * (VECTOR_SIZE - 1),
                    payload={
                        "job_id": 11,
                        "title": "Python Backend Developer",
                        "company": "Northwind",
                    },
                ),
                models.PointStruct(
                    id=12,
                    vector=[0.0, 1.0] + [0.0] * (VECTOR_SIZE - 2),
                    payload={
                        "job_id": 12,
                        "title": "React Frontend Developer",
                        "company": "Contoso",
                    },
                ),
            ],
            wait=True,
        )
        encoded_queries: list[tuple[list[str], int]] = []

        def encode_texts(texts, batch_size):
            encoded_queries.append((list(texts), batch_size))
            return [[1.0] + [0.0] * (VECTOR_SIZE - 1)]

        monkeypatch.setattr(job_search, "_encode_job_texts", encode_texts)
        results = search_jobs_semantic(
            "Python backend developer",
            top_k=2,
            client=client,
        )

        assert encoded_queries == [(["Python backend developer"], 1)]
        assert [result.job_id for result in results] == [11, 12]
        assert results[0].title == "Python Backend Developer"
        assert results[0].company == "Northwind"
        assert results[0].similarity_score == pytest.approx(1.0)
        assert results[0].similarity_score >= results[1].similarity_score
        assert client.count(COLLECTION_NAME, exact=True).count == 2
        assert search_jobs_semantic("  ", client=client) == []
    finally:
        client.close()


def test_hybrid_search_combines_rankings_deduplicates_and_sorts(monkeypatch) -> None:
    bm25_results = [
        BM25SearchResult(1, "Backend Engineer", "Northwind", 8.0),
        BM25SearchResult(1, "Duplicate Backend Engineer", "Northwind", 7.0),
        BM25SearchResult(2, "Data Engineer", "Contoso", 6.0),
    ]
    semantic_results = [
        SemanticSearchResult(3, "Python Developer", "Fabrikam", 0.9),
        SemanticSearchResult(1, "Backend Engineer", "Northwind", 0.8),
    ]

    def fake_bm25(query, top_k):
        assert query == "Python backend developer"
        assert top_k == 3
        return bm25_results

    def fake_semantic(query, top_k):
        assert query == "Python backend developer"
        assert top_k == 3
        return semantic_results

    monkeypatch.setattr(job_search, "search_jobs_bm25", fake_bm25)
    monkeypatch.setattr(job_search, "search_jobs_semantic", fake_semantic)

    results = search_jobs_hybrid("Python backend developer", top_k=3)

    assert [result.job_id for result in results] == [1, 3, 2]
    assert len({result.job_id for result in results}) == len(results)
    assert results[0].rrf_score == pytest.approx(1 / 61 + 1 / 62)
    assert results[1].rrf_score == pytest.approx(1 / 61)
    assert results[2].rrf_score == pytest.approx(1 / 63)
    assert results[0].title == "Backend Engineer"
    assert results[0].company == "Northwind"


def test_hybrid_search_handles_empty_query_and_one_empty_retriever(monkeypatch) -> None:
    calls = []

    def fake_bm25(query, top_k):
        calls.append(("bm25", query, top_k))
        return []

    def fake_semantic(query, top_k):
        calls.append(("semantic", query, top_k))
        return [SemanticSearchResult(9, "ML Engineer", "Fabrikam", 0.75)]

    monkeypatch.setattr(job_search, "search_jobs_bm25", fake_bm25)
    monkeypatch.setattr(job_search, "search_jobs_semantic", fake_semantic)

    assert search_jobs_hybrid("   ") == []
    assert calls == []

    results = search_jobs_hybrid("machine learning", top_k=4)
    assert len(results) == 1
    assert results[0].job_id == 9
    assert results[0].rrf_score == pytest.approx(1 / 61)
    assert calls == [
        ("bm25", "machine learning", 4),
        ("semantic", "machine learning", 4),
    ]
