from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.services import discovery
from app.services.job_search import (
    BM25SearchResult,
    HybridSearchResult,
    SemanticSearchResult,
)
from app.services.job_search_text import build_searchable_job_text
from tests.conftest import api_request


def add_job(session_factory: sessionmaker, **overrides) -> int:
    values = {
        "seed_key": "backend:seattle",
        "title": "Backend Engineer",
        "company": "Aster Grove Labs (Demo)",
        "category": "Backend Engineering",
        "description": "Build dependable APIs.",
        "responsibilities": ["Build APIs", "Improve reliability"],
        "required_skills": ["Python", "PostgreSQL"],
        "preferred_skills": ["Docker"],
        "min_experience_years": 2,
        "max_experience_years": 7,
        "location": "Seattle, WA",
        "work_mode": "Remote",
        "employment_type": "Full-time",
        "salary_min": 100000,
        "salary_max": 140000,
        "salary_currency": "USD",
        "is_synthetic": True,
        "data_source": "SYNTHETIC DEMO",
    }
    values.update(overrides)
    with session_factory() as session:
        job = Job(**values)
        session.add(job)
        session.commit()
        session.refresh(job)
        return job.id


def test_candidate_profile_and_ranked_jobs_api(test_app) -> None:
    app, session_factory = test_app
    data_job_id = add_job(
        session_factory,
        seed_key="data:toronto",
        title="Data Engineer",
        category="Data Engineering",
        required_skills=["Apache Spark", "Airflow"],
        preferred_skills=["dbt"],
        location="Toronto, ON",
        work_mode="Hybrid",
    )
    backend_job_id = add_job(session_factory)

    initial_profile = api_request(app, "/api/candidate")
    assert initial_profile.status_code == 200
    assert initial_profile.json()["is_configured"] is False
    assert api_request(app, "/api/jobs/picks").json()["jobs"] == []

    profile_payload = {
        "full_name": "Demo Candidate",
        "skills": ["Python", "PostgreSQL", "Docker"],
        "experience_years": 4,
        "preferred_roles": ["Backend Engineer"],
        "categories": ["Backend Engineering"],
        "locations": ["Seattle, WA"],
        "work_modes": ["Remote"],
        "employment_types": ["Full-time"],
        "profile_source": "manual",
    }
    saved = api_request(app, "/api/candidate", method="PUT", json=profile_payload)
    assert saved.status_code == 200
    assert saved.json()["is_configured"] is True
    assert saved.json()["skills"] == profile_payload["skills"]

    picks = api_request(app, "/api/jobs/picks")
    assert picks.status_code == 200
    first_ranked_id = picks.json()["jobs"][0]["id"]
    assert first_ranked_id == backend_job_id
    assert picks.json()["jobs"][0]["match"]["score"] == 100

    detail = api_request(app, f"/api/jobs/{backend_job_id}")
    assert detail.status_code == 200
    assert detail.json()["match"]["matched_skills"] == [
        "Python",
        "PostgreSQL",
        "Docker",
    ]
    assert "No confirmed resume profile is active." in detail.json()["evidence_notice"]
    assert detail.json()["data_source"] == "SYNTHETIC DEMO"

    profile_payload.update(
        {
            "skills": ["Apache Spark", "Airflow", "dbt"],
            "preferred_roles": ["Data Engineer"],
            "categories": ["Data Engineering"],
            "locations": ["Toronto, ON"],
            "work_modes": ["Hybrid"],
        }
    )
    updated = api_request(app, "/api/candidate", method="PUT", json=profile_payload)
    assert updated.status_code == 200

    changed_picks = api_request(app, "/api/jobs/picks")
    assert changed_picks.json()["jobs"][0]["id"] == data_job_id


def test_retrieval_endpoints_use_same_candidate_query_and_score_types(
    test_app,
    monkeypatch,
) -> None:
    app, session_factory = test_app
    profile_payload = {
        "full_name": "Private Candidate",
        "skills": ["Python", "PostgreSQL"],
        "experience_years": 4,
        "preferred_roles": ["Backend Engineer"],
        "categories": ["Software Engineering"],
    }
    saved = api_request(app, "/api/candidate", method="PUT", json=profile_payload)
    assert saved.status_code == 200

    with session_factory() as session:
        candidate = session.scalar(select(CandidateProfile))
        assert candidate is not None
        candidate.confirmed_profile = {
            "full_name": {"value": "Private Candidate"},
            "email": {"value": "private@example.test"},
            "phone": {"value": "+1 555 010 1234"},
            "skills": [{"value": "Computer Vision"}],
            "projects": [
                {
                    "name": {"value": "Image Search"},
                    "description": {"value": "Find objects in uploaded images"},
                    "technologies": [{"value": "PyTorch"}],
                }
            ],
            "work_experience": [
                {
                    "title": {"value": "Vision Intern"},
                    "description": {"value": "Built image classification tools"},
                    "technologies": [{"value": "OpenCV"}],
                }
            ],
        }
        session.commit()

    calls = []

    def fake_bm25(query, top_k):
        calls.append(("bm25", query, top_k))
        return [BM25SearchResult(21, "Backend Engineer", "Northwind", 3.5)]

    def fake_semantic(query, top_k):
        calls.append(("semantic", query, top_k))
        return [SemanticSearchResult(22, "Vision Engineer", "Contoso", 0.82)]

    def fake_hybrid(query, top_k):
        calls.append(("hybrid", query, top_k))
        return [HybridSearchResult(23, "ML Engineer", "Fabrikam", 0.03)]

    monkeypatch.setattr(discovery, "search_jobs_bm25", fake_bm25)
    monkeypatch.setattr(discovery, "search_jobs_semantic", fake_semantic)
    monkeypatch.setattr(discovery, "search_jobs_hybrid", fake_hybrid)

    endpoints = [
        (
            "/api/jobs/retrieval/bm25",
            "bm25",
            3.5,
            21,
            "Backend Engineer",
            "Northwind",
        ),
        (
            "/api/jobs/retrieval/semantic",
            "semantic_similarity",
            0.82,
            22,
            "Vision Engineer",
            "Contoso",
        ),
        (
            "/api/jobs/retrieval/hybrid",
            "rrf",
            0.03,
            23,
            "ML Engineer",
            "Fabrikam",
        ),
    ]
    for path, score_type, score, job_id, title, company in endpoints:
        response = api_request(app, f"{path}?top_k=7")
        assert response.status_code == 200
        body = response.json()
        assert body["profile_configured"] is True
        assert body["query_available"] is True
        assert body["score_type"] == score_type
        assert body["total"] == 1
        assert body["jobs"] == [
            {
                "id": job_id,
                "title": title,
                "company": company,
                "score": score,
            }
        ]

    queries = [query for _, query, _ in calls]
    assert [mode for mode, _, _ in calls] == ["bm25", "semantic", "hybrid"]
    assert len(set(queries)) == 1
    assert all(top_k == 7 for _, _, top_k in calls)
    query = queries[0]
    for expected in (
        "Python",
        "PostgreSQL",
        "Backend Engineer",
        "Image Search",
        "PyTorch",
        "Vision Intern",
        "OpenCV",
    ):
        assert expected in query
    for private_value in (
        "Private Candidate",
        "private@example.test",
        "+1 555 010 1234",
    ):
        assert private_value not in query
    assert query.count("Python") == 1


def test_retrieval_endpoints_handle_unconfigured_profile_and_empty_results(
    test_app,
    monkeypatch,
) -> None:
    app, _ = test_app
    called = []

    def unexpected_call(query, top_k):
        called.append((query, top_k))
        return []

    monkeypatch.setattr(discovery, "search_jobs_bm25", unexpected_call)
    monkeypatch.setattr(discovery, "search_jobs_semantic", unexpected_call)
    monkeypatch.setattr(discovery, "search_jobs_hybrid", unexpected_call)

    paths = (
        "/api/jobs/retrieval/bm25",
        "/api/jobs/retrieval/semantic",
        "/api/jobs/retrieval/hybrid",
    )
    for path in paths:
        response = api_request(app, path)
        assert response.status_code == 200
        assert response.json()["profile_configured"] is False
        assert response.json()["query_available"] is False
        assert response.json()["total"] == 0
        assert response.json()["jobs"] == []
    assert called == []

    saved = api_request(
        app,
        "/api/candidate",
        method="PUT",
        json={"skills": ["Python"], "preferred_roles": ["Backend Engineer"]},
    )
    assert saved.status_code == 200

    for path in paths:
        response = api_request(app, path)
        assert response.status_code == 200
        assert response.json()["profile_configured"] is True
        assert response.json()["query_available"] is True
        assert response.json()["total"] == 0
        assert response.json()["jobs"] == []
    assert len(called) == 3
    assert len({query for query, _ in called}) == 1
    assert all(top_k == 10 for _, top_k in called)


def test_retrieval_query_ignores_contact_only_candidate_data(test_app, monkeypatch) -> None:
    app, session_factory = test_app
    initial = api_request(app, "/api/candidate")
    assert initial.status_code == 200
    with session_factory() as session:
        candidate = session.scalar(select(CandidateProfile))
        assert candidate is not None
        candidate.is_configured = True
        candidate.skills = []
        candidate.preferred_roles = []
        candidate.categories = []
        candidate.experience_years = None
        candidate.confirmed_profile = {
            "full_name": {"value": "Private Candidate"},
            "email": {"value": "private@example.test"},
            "phone": {"value": "+1 555 010 1234"},
        }
        session.commit()

    def unexpected_call(query, top_k):
        raise AssertionError("Retrieval should not run with a contact-only profile.")

    monkeypatch.setattr(discovery, "search_jobs_bm25", unexpected_call)
    monkeypatch.setattr(discovery, "search_jobs_semantic", unexpected_call)
    monkeypatch.setattr(discovery, "search_jobs_hybrid", unexpected_call)

    response = api_request(app, "/api/jobs/retrieval/bm25")

    assert response.status_code == 200
    assert response.json()["profile_configured"] is True
    assert response.json()["query_available"] is False
    assert response.json()["jobs"] == []


def test_job_detail_returns_not_found(test_app) -> None:
    app, _ = test_app

    response = api_request(app, "/api/jobs/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found."


def test_searchable_job_text_handles_missing_fields_and_duplicate_content() -> None:
    searchable_text = build_searchable_job_text(
        title="  Backend   Engineer ",
        company="Demo Company",
        description="Build dependable APIs.",
        required_skills=["Python", " python ", "PostgreSQL"],
        preferred_skills=None,
        responsibilities=[
            "Build dependable APIs.",
            "  Improve   reliability. ",
            "Improve reliability.",
        ],
        min_experience_years=2,
        max_experience_years=7,
        employment_type="Full-time",
        location="Seattle, WA",
        work_mode="Remote",
    )

    assert "Title: Backend Engineer" in searchable_text
    assert "Required skills: Python, PostgreSQL" in searchable_text
    assert "Preferred skills:" not in searchable_text
    assert searchable_text.count("Build dependable APIs.") == 1
    assert searchable_text.count("Improve reliability.") == 1
    assert "Experience: 2-7 years" in searchable_text


def test_jobs_get_searchable_text_on_insert_and_refresh_on_update(test_app) -> None:
    _, session_factory = test_app
    job_id = add_job(session_factory)

    with session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert "Title: Backend Engineer" in job.searchable_text
        assert "Company: Aster Grove Labs (Demo)" in job.searchable_text
        assert "Required skills: Python, PostgreSQL" in job.searchable_text
        assert "Responsibilities:\n- Build APIs\n- Improve reliability" in job.searchable_text
        assert "Location: Seattle, WA" in job.searchable_text
        assert "Work mode: Remote" in job.searchable_text

        job.title = "Senior Backend Engineer"
        job.description = "Operate resilient API services."
        job.required_skills = ["Python", "SQL"]
        session.commit()
        session.refresh(job)

        assert "Title: Senior Backend Engineer" in job.searchable_text
        assert "Description: Operate resilient API services." in job.searchable_text
        assert "Required skills: Python, SQL" in job.searchable_text
        assert "Required skills: Python, PostgreSQL" not in job.searchable_text


def test_candidate_profile_rejects_out_of_range_experience(test_app) -> None:
    app, _ = test_app

    response = api_request(
        app,
        "/api/candidate",
        method="PUT",
        json={"experience_years": 61},
    )

    assert response.status_code == 422


def test_cors_preflight_allows_vite_loopback_origin(test_app) -> None:
    app, _ = test_app

    response = api_request(
        app,
        "/api/candidate",
        method="OPTIONS",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
