from qdrant_client import QdrantClient, models

from app.models.job import Job
from app.services.job_embeddings import (
    COLLECTION_NAME,
    VECTOR_SIZE,
    index_jobs,
)


def _add_job(session_factory) -> int:
    with session_factory() as session:
        job = Job(
            seed_key="embedding:test",
            title="Backend Engineer",
            company="Example Company",
            category="Engineering",
            description="Build dependable APIs.",
            responsibilities=["Improve reliability."],
            required_skills=["Python", "PostgreSQL"],
            preferred_skills=["Docker"],
            min_experience_years=2,
            max_experience_years=7,
            location="Seattle, WA",
            work_mode="Remote",
            employment_type="Full-time",
        )
        session.add(job)
        session.commit()
        return job.id


def test_indexing_upserts_payload_and_skips_unchanged_text(test_app) -> None:
    _, session_factory = test_app
    job_id = _add_job(session_factory)
    client = QdrantClient(":memory:")
    encoder_calls: list[list[str]] = []

    def encoder(texts, batch_size):
        encoder_calls.append(list(texts))
        return [[1.0] + [0.0] * (VECTOR_SIZE - 1) for _ in texts]

    try:
        with session_factory() as session:
            first = index_jobs(session, client=client, encode_texts=encoder)
        assert first.total_jobs == 1
        assert first.successful == 1
        assert first.failed == 0
        assert first.upserted == 1

        collection = client.get_collection(COLLECTION_NAME)
        assert collection.config.params.vectors.size == VECTOR_SIZE
        assert collection.config.params.vectors.distance == models.Distance.COSINE
        point = client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[job_id],
            with_payload=True,
            with_vectors=True,
        )[0]
        assert point.id == job_id
        assert point.payload["job_id"] == job_id
        assert point.payload["title"] == "Backend Engineer"
        assert point.payload["company"] == "Example Company"
        assert point.payload["location"] == "Seattle, WA"
        assert point.payload["employment_type"] == "Full-time"
        assert point.payload["required_skills"] == ["Python", "PostgreSQL"]
        assert "Build dependable APIs." in point.payload["searchable_text"]
        assert (
            point.payload["embedding_model"]
            == "sentence-transformers/all-MiniLM-L6-v2"
        )
        assert len(point.vector) == VECTOR_SIZE

        with session_factory() as session:
            second = index_jobs(session, client=client, encode_texts=encoder)
        assert second.successful == 1
        assert second.unchanged == 1
        assert second.upserted == 0
        assert len(encoder_calls) == 1
        assert client.count(COLLECTION_NAME).count == 1

        with session_factory() as session:
            job = session.get(Job, job_id)
            assert job is not None
            job.description = "Build reliable data services."
            session.commit()

        with session_factory() as session:
            updated = index_jobs(session, client=client, encode_texts=encoder)
        assert updated.successful == 1
        assert updated.upserted == 1
        assert len(encoder_calls) == 2
        refreshed = client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[job_id],
            with_payload=True,
            with_vectors=False,
        )[0]
        assert "Build reliable data services." in refreshed.payload["searchable_text"]
        assert client.count(COLLECTION_NAME).count == 1
    finally:
        client.close()
