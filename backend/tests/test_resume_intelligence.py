import asyncio
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pymupdf
import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.resume import ResumeVersion
from app.schemas.resumes import ResumeExtraction
from app.services.resume_evaluation import evaluate_prediction, summarize_evaluation
from app.services.resume_parser import parse_resume_text
from app.services.resumes import run_resume_extraction
from app.services.resume_pdf import OCRUnsupportedError, PDFValidationError, extract_pdf_text
from tests.conftest import api_request


def _pdf(text: str | None = None, *, image_only: bool = False) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    if image_only:
        image = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l2cAAAAASUVORK5CYII="
        )
        page.insert_image(page.rect, stream=image)
    elif text:
        page.insert_text((72, 72), text)
    result = document.tobytes()
    document.close()
    return result


def _configure_resume_test(monkeypatch, storage_dir: Path, session_factory) -> None:
    settings = Settings(resume_storage_dir=storage_dir)
    monkeypatch.setattr("app.api.routes.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.resumes.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.resumes.SessionLocal", session_factory)


def test_local_parser_extracts_explicit_resume_facts_with_evidence() -> None:
    source = (
        "Alex Morgan\n"
        "Email: alex.morgan@example.test\n"
        "Phone: +1 (206) 555-0142\n"
        "Experience: 4 years\n"
        "Technical Skills: Python, FastAPI, PostgreSQL\n"
    )
    extraction = parse_resume_text(source)

    assert extraction.full_name.value == "Alex Morgan"
    assert extraction.email.value == "alex.morgan@example.test"
    assert extraction.phone is not None
    assert "206" in extraction.phone.value
    assert extraction.total_experience_years.value == 4
    assert {skill.name for skill in extraction.skills} == {
        "Python",
        "FastAPI",
        "PostgreSQL",
    }
    assert all(
        item.snippet in source
        for skill in extraction.skills
        for item in skill.evidence
    )


def test_background_local_extraction_completes_once(test_app, monkeypatch) -> None:
    _, session_factory = test_app
    monkeypatch.setattr("app.services.resumes.SessionLocal", session_factory)
    with session_factory() as session:
        session.add(CandidateProfile(id=1, full_name="Candidate"))
        resume = ResumeVersion(
            candidate_profile_id=1,
            original_filename="synthetic.pdf",
            storage_filename="synthetic-retry-test.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="c" * 64,
            extraction_status="queued",
            extracted_text="Alex Morgan\nSkills: Python",
        )
        session.add(resume)
        session.commit()
        resume_id = resume.id

    run_resume_extraction(resume_id)
    run_resume_extraction(resume_id)

    with session_factory() as session:
        resume = session.get(ResumeVersion, resume_id)
        assert resume is not None
        assert resume.extraction_status == "needs_review"
        assert resume.extraction_attempts == 1
        assert resume.extracted_text == "Alex Morgan\nSkills: Python"
        assert resume.extracted_data["skills"][0]["name"] == "Python"


def test_retry_endpoint_queues_failed_resume_only_once(
    test_app, monkeypatch
) -> None:
    app, session_factory = test_app
    monkeypatch.setattr("app.services.resumes.SessionLocal", session_factory)
    with session_factory() as session:
        session.add(CandidateProfile(id=1, full_name="Candidate"))
        resume = ResumeVersion(
            candidate_profile_id=1,
            original_filename="synthetic.pdf",
            storage_filename="synthetic-manual-retry.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="e" * 64,
            extraction_status="failed",
            extraction_error="service_unavailable",
            extraction_failure_category="service_unavailable",
            extraction_http_status=503,
            extraction_retryable=True,
            extracted_text="Skills: Python",
        )
        session.add(resume)
        session.commit()
        resume_id = resume.id

    response = api_request(app, f"/api/resumes/{resume_id}/extract", method="POST")

    assert response.status_code == 202
    assert response.json()["extraction_status"] == "queued"
    with session_factory() as session:
        stored = session.get(ResumeVersion, resume_id)
        assert stored is not None
        assert stored.extraction_status == "needs_review"
        assert stored.extraction_http_status is None
    duplicate = api_request(app, f"/api/resumes/{resume_id}/extract", method="POST")
    assert duplicate.status_code == 409
    assert stored.extracted_data["skills"][0]["name"] == "Python"


def test_startup_recovers_only_stale_resumes_and_retry_endpoint_reuses_saved_pdf(
    test_app, monkeypatch, tmp_path
) -> None:
    app, session_factory = test_app
    settings = Settings(
        resume_processing_stale_seconds=600,
    )
    monkeypatch.setattr("app.main.SessionLocal", session_factory)
    monkeypatch.setattr("app.services.resumes.SessionLocal", session_factory)
    monkeypatch.setattr("app.services.resumes.get_settings", lambda: settings)

    now = datetime.now(timezone.utc)
    old_pdf = tmp_path / "orphaned-resume.pdf"
    recent_pdf = tmp_path / "recent-resume.pdf"
    old_pdf.write_bytes(b"preserved synthetic PDF")
    recent_pdf.write_bytes(b"recent synthetic PDF")

    with session_factory() as session:
        profile = CandidateProfile(id=1, full_name="Candidate")
        session.add(profile)
        orphaned = ResumeVersion(
            candidate_profile_id=1,
            original_filename="orphaned.pdf",
            storage_filename=old_pdf.name,
            content_type="application/pdf",
            size_bytes=old_pdf.stat().st_size,
            sha256="a" * 64,
            extraction_status="processing",
            extraction_attempts=2,
            uploaded_at=now - timedelta(minutes=20),
            processing_started_at=None,
            extracted_text="Skills: Python",
        )
        recent = ResumeVersion(
            candidate_profile_id=1,
            original_filename="recent.pdf",
            storage_filename=recent_pdf.name,
            content_type="application/pdf",
            size_bytes=recent_pdf.stat().st_size,
            sha256="b" * 64,
            extraction_status="processing",
            extraction_attempts=1,
            uploaded_at=now - timedelta(seconds=30),
            processing_started_at=now - timedelta(seconds=30),
            extracted_text="Skills: Python",
        )
        session.add_all([orphaned, recent])
        session.commit()
        orphaned_id, recent_id = orphaned.id, recent.id
        original_profile_name = profile.full_name

    async def run_startup() -> None:
        async with app.router.lifespan_context(app):
            pass

    asyncio.run(run_startup())

    with session_factory() as session:
        orphaned = session.get(ResumeVersion, orphaned_id)
        recent = session.get(ResumeVersion, recent_id)
        profile = session.get(CandidateProfile, 1)
        assert orphaned is not None
        assert orphaned.extraction_status == "failed"
        assert orphaned.extraction_failure_category == "worker_lost"
        assert orphaned.extraction_retryable is True
        assert orphaned.extraction_attempts == 2
        assert recent is not None
        assert recent.extraction_status == "processing"
        assert profile is not None
        assert profile.full_name == original_profile_name
    assert old_pdf.read_bytes() == b"preserved synthetic PDF"

    response = api_request(
        app, f"/api/resumes/{orphaned_id}/extract", method="POST"
    )
    assert response.status_code == 202
    assert response.json()["extraction_status"] == "queued"

    with session_factory() as session:
        orphaned = session.get(ResumeVersion, orphaned_id)
        assert orphaned is not None
        assert orphaned.extraction_status == "needs_review"
        assert orphaned.extraction_attempts == 1
        assert orphaned.extracted_text == "Skills: Python"
        assert orphaned.extracted_data["skills"][0]["name"] == "Python"
        assert session.get(CandidateProfile, 1).full_name == original_profile_name
    assert old_pdf.read_bytes() == b"preserved synthetic PDF"

    duplicate = api_request(
        app, f"/api/resumes/{orphaned_id}/extract", method="POST"
    )
    assert duplicate.status_code == 409
    assert old_pdf.read_bytes() == b"preserved synthetic PDF"


def test_local_parser_failure_is_actionable_and_preserves_source(
    test_app, monkeypatch, tmp_path
) -> None:
    _, session_factory = test_app
    settings = Settings(
        resume_storage_dir=tmp_path,
    )
    monkeypatch.setattr("app.services.resumes.SessionLocal", session_factory)
    monkeypatch.setattr("app.services.resumes.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.services.resumes.parse_resume_text",
        lambda *_: (_ for _ in ()).throw(ValueError("synthetic private source")),
    )
    stored_pdf = tmp_path / "synthetic-failure.pdf"
    stored_pdf.write_bytes(_pdf("Skills: Python"))
    with session_factory() as session:
        session.add(CandidateProfile(id=1, full_name="Candidate"))
        resume = ResumeVersion(
            candidate_profile_id=1,
            original_filename="synthetic.pdf",
            storage_filename=stored_pdf.name,
            content_type="application/pdf",
            size_bytes=stored_pdf.stat().st_size,
            sha256="d" * 64,
            extraction_status="queued",
            extracted_text="Skills: Python",
        )
        session.add(resume)
        session.commit()
        resume_id = resume.id

    run_resume_extraction(resume_id)

    with session_factory() as session:
        resume = session.get(ResumeVersion, resume_id)
        assert resume is not None
        assert resume.extraction_status == "failed"
        assert resume.extraction_failure_category == "parse_error"
        assert resume.extraction_http_status is None
        assert resume.extraction_retryable is True
        assert resume.extraction_attempts == 1
        assert "synthetic private source" not in resume.extraction_diagnostic
        assert resume.extracted_text == "Skills: Python"
        assert stored_pdf.exists()


def _api_upload(app, content: bytes, *, filename: str = "resume.pdf", mime: str = "application/pdf"):
    import asyncio

    import httpx

    async def perform_request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/api/resumes",
                files={"file": (filename, content, mime)},
            )

    return asyncio.run(perform_request())


def test_pdf_validation_distinguishes_invalid_empty_and_scanned_documents() -> None:
    with pytest.raises(PDFValidationError):
        extract_pdf_text(b"", max_pages=5, max_characters=1000)
    with pytest.raises(PDFValidationError):
        extract_pdf_text(b"not a pdf", max_pages=5, max_characters=1000)
    with pytest.raises(OCRUnsupportedError):
        extract_pdf_text(_pdf(image_only=True), max_pages=5, max_characters=1000)


def test_resume_upload_extracts_text_locally_without_external_configuration(
    test_app, monkeypatch, tmp_path
) -> None:
    app, _ = test_app
    _configure_resume_test(monkeypatch, tmp_path, test_app[1])

    response = _api_upload(app, _pdf("Alex Morgan\nPython"))

    assert response.status_code == 202
    resume = response.json()
    assert resume["extraction_status"] == "queued"
    assert len(list(tmp_path.glob("*.pdf"))) == 1
    with test_app[1]() as session:
        stored = session.scalar(select(ResumeVersion).where(ResumeVersion.id == resume["id"]))
        assert stored is not None
        assert stored.extraction_status == "needs_review"
        assert stored.extraction_failure_category is None
        assert stored.extracted_text == "Alex Morgan\nPython"
        assert stored.extracted_data["full_name"]["value"] == "Alex Morgan"


def test_resume_upload_rejects_wrong_extension_and_malformed_pdf(
    test_app, monkeypatch, tmp_path
) -> None:
    app, _ = test_app
    _configure_resume_test(monkeypatch, tmp_path, test_app[1])

    wrong_extension = _api_upload(app, _pdf("Text"), filename="resume.txt")
    malformed = _api_upload(app, b"not a pdf")

    assert wrong_extension.status_code == 415
    assert malformed.status_code == 422
    assert list(tmp_path.iterdir()) == []


def test_resume_upload_rejects_wrong_mime_empty_and_oversized_content(
    test_app, monkeypatch, tmp_path
) -> None:
    app, _ = test_app
    settings = Settings(
        resume_storage_dir=tmp_path,
        max_resume_size_bytes=1024,
    )
    monkeypatch.setattr("app.api.routes.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.resumes.get_settings", lambda: settings)

    wrong_mime = _api_upload(app, _pdf("Text"), mime="text/plain")
    empty = _api_upload(app, b"")
    oversized = _api_upload(app, b"x" * 1025)

    assert wrong_mime.status_code == 415
    assert empty.status_code == 422
    assert oversized.status_code == 413
    assert list(tmp_path.iterdir()) == []


def test_scanned_resume_is_saved_with_explicit_ocr_status(
    test_app, monkeypatch, tmp_path
) -> None:
    app, _ = test_app
    _configure_resume_test(monkeypatch, tmp_path, test_app[1])

    response = _api_upload(app, _pdf(image_only=True))

    assert response.status_code == 202
    assert response.json()["extraction_status"] == "ocr_unsupported"
    assert "OCR is not supported" in response.json()["message"]


def test_confirmed_resume_updates_matching_profile_and_preserves_preferences(
    test_app, monkeypatch, tmp_path
) -> None:
    app, session_factory = test_app
    _configure_resume_test(monkeypatch, tmp_path, session_factory)
    preferences = {
        "locations": ["Seattle, WA"],
        "work_modes": ["Remote"],
        "employment_types": ["Full-time"],
        "salary_min": 90000,
        "salary_max": 150000,
        "salary_currency": "USD",
    }
    assert api_request(app, "/api/preferences", method="PUT", json=preferences).status_code == 200

    extraction = ResumeExtraction.model_validate(
        {
            "skills": [
                {
                    "name": "Python",
                    "category": "technical",
                    "evidence": [{"snippet": "Skills: Python"}],
                }
            ]
        }
    )
    with session_factory() as session:
        resume = ResumeVersion(
            candidate_profile_id=1,
            original_filename="resume.pdf",
            storage_filename="test-resume.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="a" * 64,
            extraction_status="needs_review",
            extracted_text="Alex Morgan\nSkills: Python",
            extracted_data=extraction.model_dump(mode="json"),
        )
        session.add(resume)
        session.commit()
        resume_id = resume.id

    confirmed_payload = {
        "full_name": {
            "value": "Alex Morgan",
            "source": "resume",
            "evidence": [{"snippet": "Alex Morgan"}],
        },
        "skills": [
            {
                "value": "Python",
                "category": "technical",
                "source": "resume",
                "evidence": [{"snippet": "Skills: Python"}],
            }
        ],
        "manual_skills": ["Kubernetes"],
    }
    response = api_request(
        app,
        f"/api/resumes/{resume_id}/confirm",
        method="PUT",
        json=confirmed_payload,
    )

    assert response.status_code == 200
    assert response.json()["is_confirmed"] is True
    candidate = api_request(app, "/api/candidate").json()
    assert candidate["skills"] == ["Python", "Kubernetes"]
    assert candidate["profile_source"] == "resume_confirmed"
    assert api_request(app, "/api/preferences").json() == preferences

    job = Job(
        seed_key="resume-test:job",
        title="Backend Engineer",
        company="Demo Company",
        category="Backend Engineering",
        description="Build APIs.",
        responsibilities=["Build APIs"],
        required_skills=["Python"],
        preferred_skills=[],
        min_experience_years=0,
        max_experience_years=5,
        location="Seattle, WA",
        work_mode="Remote",
        employment_type="Full-time",
        is_synthetic=True,
        data_source="SYNTHETIC DEMO",
    )
    with session_factory() as session:
        session.add(job)
        session.commit()
        job_id = job.id
    detail = api_request(app, f"/api/jobs/{job_id}").json()
    evidence = next(item for item in detail["match"]["skill_evidence"] if item["skill"] == "Python")
    assert evidence == {
        "skill": "Python",
        "source": "resume",
        "evidence": ["Skills: Python"],
    }


def test_confirmation_rejects_unsupported_resume_evidence(test_app) -> None:
    app, session_factory = test_app
    with session_factory() as session:
        session.add(CandidateProfile(id=1, full_name="Candidate"))
        resume = ResumeVersion(
            candidate_profile_id=1,
            original_filename="resume.pdf",
            storage_filename="unsupported-resume.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="b" * 64,
            extraction_status="needs_review",
            extracted_text="Skills: Python",
            extracted_data={"skills": []},
        )
        session.add(resume)
        session.commit()
        resume_id = resume.id

    response = api_request(
        app,
        f"/api/resumes/{resume_id}/confirm",
        method="PUT",
        json={
            "skills": [
                {
                    "value": "Go",
                    "source": "resume",
                    "evidence": [{"snippet": "Go developer"}],
                }
            ]
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"].startswith("A resume-sourced fact")
    with session_factory() as session:
        resume = session.scalar(select(ResumeVersion).where(ResumeVersion.id == resume_id))
        assert resume is not None
        assert resume.is_confirmed is False


def test_resume_evaluation_reports_skill_field_and_evidence_metrics() -> None:
    source = "Alex Morgan\nSkills: Python"
    extraction = ResumeExtraction.model_validate(
        {
            "full_name": {
                "value": "Alex Morgan",
                "evidence": [{"snippet": "Alex Morgan"}],
            },
            "skills": [
                {
                    "name": "Python",
                    "category": "technical",
                    "evidence": [{"snippet": "Skills: Python"}],
                },
                {
                    "name": "InventedSkill",
                    "category": "technical",
                    "evidence": [{"snippet": "not present"}],
                },
            ],
        }
    )

    record = evaluate_prediction(
        {"skills": ["Python"], "fields": {"full_name": "Alex Morgan"}},
        extraction,
        source,
    )
    metrics = summarize_evaluation([record])

    assert metrics["skill_precision"] == 0.5
    assert metrics["skill_recall"] == 1.0
    assert metrics["field_level_accuracy"] == pytest.approx(8 / 9, abs=0.0001)
    assert metrics["field_metrics"]["full_name"]["exact_accuracy"] == 1.0
    assert metrics["evidence_coverage"] < 1.0
    assert metrics["unsupported_claim_rate"] > 0.0
    assert metrics["structured_output_validation_failure_rate"] == 0.0
