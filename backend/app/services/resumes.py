import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT, Settings, get_settings
from app.database.session import SessionLocal
from app.models.candidate import CandidateProfile
from app.models.resume import ResumeVersion
from app.schemas.resumes import (
    CandidatePreferences,
    ConfirmedCandidateProfile,
    ResumeDetail,
    ResumeExtraction,
    ResumeListItem,
)
from app.services.profiles import DEMO_CANDIDATE_ID, get_candidate_profile
from app.services.resume_parser import parse_resume_text
from app.services.resume_pdf import (
    OCRUnsupportedError,
    PDFValidationError,
    extract_pdf_text,
)
from app.services.resume_validation import (
    UnsupportedEvidenceError,
    build_review_profile,
    validate_confirmed_profile,
    validate_extraction,
)

logger = logging.getLogger(__name__)

RESUME_MESSAGES = {
    "needs_review": "Extraction finished. Review and confirm the candidate profile.",
    "ocr_unsupported": "This scanned PDF was saved, but OCR is not supported.",
    "queued": "The PDF is saved. Resume extraction has been queued.",
    "processing": "Resume extraction is in progress.",
    "failed": "The PDF and extracted text are saved. Review the failure details before retrying.",
}


def _storage_directory(settings: Settings) -> Path:
    directory = settings.resume_storage_dir
    if not directory.is_absolute():
        directory = PROJECT_ROOT / directory
    return directory.resolve()


def _private_file_path(filename: str, settings: Settings | None = None) -> Path:
    return _storage_directory(settings or get_settings()) / filename


def _safe_original_filename(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name:
        return "resume.pdf"
    return name[:255]


def _resume_payload(
    resume: ResumeVersion, *, message: str | None = None
) -> ResumeDetail:
    extraction = (
        ResumeExtraction.model_validate(resume.extracted_data)
        if resume.extracted_data
        else None
    )
    review_profile = None
    if resume.is_confirmed and resume.confirmed_data:
        review_profile = ConfirmedCandidateProfile.model_validate(
            resume.confirmed_data
        )
    elif extraction:
        review_profile = build_review_profile(extraction)
    message = message or RESUME_MESSAGES.get(resume.extraction_status)
    return ResumeDetail(
        id=resume.id,
        original_filename=resume.original_filename,
        size_bytes=resume.size_bytes,
        extraction_status=resume.extraction_status,
        extraction_error=resume.extraction_error,
        failure_category=resume.extraction_failure_category,
        http_status=resume.extraction_http_status,
        diagnostic=resume.extraction_diagnostic,
        retryable=resume.extraction_retryable is True
        or (
            resume.extraction_status == "failed"
            and resume.extraction_retryable is None
        ),
        attempts=resume.extraction_attempts,
        is_confirmed=resume.is_confirmed,
        uploaded_at=resume.uploaded_at,
        extracted_at=resume.extracted_at,
        confirmed_at=resume.confirmed_at,
        extracted_data=extraction,
        validation_report=resume.validation_report,
        review_profile=review_profile,
        message=message,
    )


def _record_failure(
    resume: ResumeVersion,
    *,
    category: str,
    retryable: bool,
    diagnostic: str,
) -> None:
    resume.extraction_status = "failed"
    resume.extraction_error = category
    resume.extraction_failure_category = category
    resume.extraction_http_status = None
    resume.extraction_retryable = retryable
    resume.extraction_diagnostic = diagnostic[:300]


def _run_extraction(
    resume: ResumeVersion,
    session: Session,
) -> None:
    if not resume.extracted_text:
        _record_failure(
            resume,
            category="missing_text",
            retryable=False,
            diagnostic="No extracted PDF text is available for processing.",
        )
        session.commit()
        return

    resume.extraction_attempts += 1
    session.commit()
    try:
        extraction = parse_resume_text(resume.extracted_text)
        resume.extracted_data = extraction.model_dump(mode="json")
        resume.validation_report = validate_extraction(
            extraction, resume.extracted_text
        )
    except Exception as exc:
        logger.error("Local resume parsing failed (%s).", type(exc).__name__)
        _record_failure(
            resume,
            category="parse_error",
            retryable=True,
            diagnostic=(
                "Local extraction failed unexpectedly. Retry once or enter "
                "the profile details manually."
            ),
        )
        session.commit()
        return

    resume.extraction_status = "needs_review"
    resume.extraction_error = None
    resume.extraction_failure_category = None
    resume.extraction_http_status = None
    resume.extraction_diagnostic = None
    resume.extraction_retryable = None
    resume.extracted_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(resume)


def run_resume_extraction(resume_id: int) -> None:
    """Claim and process a queued resume once, using a fresh worker session."""
    with SessionLocal() as session:
        result = session.execute(
            update(ResumeVersion)
            .where(
                ResumeVersion.id == resume_id,
                ResumeVersion.extraction_status == "queued",
            )
            .values(
                extraction_status="processing",
                processing_started_at=datetime.now(timezone.utc),
            )
        )
        if result.rowcount != 1:
            session.rollback()
            return
        session.commit()
        resume = session.get(ResumeVersion, resume_id)
        if resume is not None:
            _run_extraction(resume, session)


def recover_stale_resume_extractions(
    session: Session,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int:
    """Mark only overdue in-process tasks retryable; never enqueue them here."""
    settings = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    stale_before = now - timedelta(
        seconds=settings.resume_processing_stale_seconds
    )
    result = session.execute(
        update(ResumeVersion)
        .where(
            ResumeVersion.extraction_status == "processing",
            func.coalesce(
                ResumeVersion.processing_started_at,
                ResumeVersion.uploaded_at,
            )
            < stale_before,
        )
        .values(
            extraction_status="failed",
            extraction_error="worker_lost",
            extraction_failure_category="worker_lost",
            extraction_http_status=None,
            extraction_diagnostic=(
                "The background worker stopped before recording a result. "
                "The saved resume can be retried."
            ),
            extraction_retryable=True,
        )
    )
    session.commit()
    return result.rowcount or 0


def create_resume(
    session: Session,
    *,
    original_filename: str,
    content_type: str,
    content: bytes,
) -> ResumeDetail:
    settings = get_settings()
    try:
        extracted = extract_pdf_text(
            content,
            max_pages=settings.max_resume_pages,
            max_characters=settings.max_resume_text_chars,
        )
        status = "queued"
        extracted_text: str | None = extracted.text
        extraction_error = None
    except OCRUnsupportedError:
        status = "ocr_unsupported"
        extracted_text = ""
        extraction_error = "ocr_unsupported"
    except PDFValidationError:
        raise

    storage_filename = f"{uuid.uuid4().hex}.pdf"
    storage_directory = _storage_directory(settings)
    storage_directory.mkdir(parents=True, exist_ok=True)
    file_path = storage_directory / storage_filename
    file_descriptor = os.open(
        file_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(file_descriptor, "wb") as resume_file:
            resume_file.write(content)
        profile = get_candidate_profile(session)
        resume = ResumeVersion(
            candidate_profile_id=profile.id,
            original_filename=_safe_original_filename(original_filename),
            storage_filename=storage_filename,
            content_type=content_type,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            extraction_status=status,
            extraction_error=extraction_error,
            extraction_attempts=0,
            extracted_text=extracted_text,
        )
        session.add(resume)
        session.commit()
        session.refresh(resume)
    except Exception:
        session.rollback()
        file_path.unlink(missing_ok=True)
        raise

    return _resume_payload(resume)


def list_resumes(session: Session) -> list[ResumeListItem]:
    records = session.scalars(
        select(ResumeVersion)
        .where(ResumeVersion.candidate_profile_id == DEMO_CANDIDATE_ID)
        .order_by(ResumeVersion.uploaded_at.desc(), ResumeVersion.id.desc())
    ).all()
    return [
        ResumeListItem(
            id=resume.id,
            original_filename=resume.original_filename,
            size_bytes=resume.size_bytes,
            extraction_status=resume.extraction_status,
            extraction_error=resume.extraction_error,
            failure_category=resume.extraction_failure_category,
            http_status=resume.extraction_http_status,
            diagnostic=resume.extraction_diagnostic,
            retryable=resume.extraction_retryable is True
            or (
                resume.extraction_status == "failed"
                and resume.extraction_retryable is None
            ),
            attempts=resume.extraction_attempts,
            is_confirmed=resume.is_confirmed,
            uploaded_at=resume.uploaded_at,
            extracted_at=resume.extracted_at,
            confirmed_at=resume.confirmed_at,
        )
        for resume in records
    ]


def get_resume(session: Session, resume_id: int) -> ResumeDetail | None:
    resume = session.scalar(
        select(ResumeVersion).where(
            ResumeVersion.id == resume_id,
            ResumeVersion.candidate_profile_id == DEMO_CANDIDATE_ID,
        )
    )
    return _resume_payload(resume) if resume else None


def retry_resume_extraction(
    session: Session, resume_id: int
) -> ResumeDetail | None:
    resume = session.scalar(
        select(ResumeVersion).where(
            ResumeVersion.id == resume_id,
            ResumeVersion.candidate_profile_id == DEMO_CANDIDATE_ID,
        )
    )
    if resume is None:
        return None
    if resume.extraction_status != "failed":
        raise ValueError("Only failed resumes can be retried.")
    if resume.extraction_retryable is False:
        raise ValueError("This extraction failure is permanent and cannot be retried.")
    result = session.execute(
        update(ResumeVersion)
        .where(
            ResumeVersion.id == resume_id,
            ResumeVersion.candidate_profile_id == DEMO_CANDIDATE_ID,
            ResumeVersion.extraction_status == "failed",
            or_(
                ResumeVersion.extraction_retryable.is_(None),
                ResumeVersion.extraction_retryable.is_(True),
            ),
        )
        .values(
            extraction_status="queued",
            extraction_error=None,
            extraction_failure_category=None,
            extraction_http_status=None,
            extraction_diagnostic=None,
            extraction_retryable=None,
            extraction_attempts=0,
            processing_started_at=None,
        )
    )
    if result.rowcount != 1:
        session.rollback()
        raise ValueError("Resume is no longer eligible for retry.")
    session.commit()
    return get_resume(session, resume_id)


def _clean_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            result.append(cleaned)
            seen.add(key)
    return result


def _resume_profile_skills(profile: ConfirmedCandidateProfile) -> list[str]:
    return _clean_strings(
        [skill.value for skill in profile.skills] + profile.manual_skills
    )


def confirm_resume_profile(
    session: Session,
    resume_id: int,
    candidate_data: ConfirmedCandidateProfile,
) -> ResumeDetail | None:
    resume = session.scalar(
        select(ResumeVersion).where(
            ResumeVersion.id == resume_id,
            ResumeVersion.candidate_profile_id == DEMO_CANDIDATE_ID,
        )
    )
    if resume is None:
        return None
    if resume.extraction_status != "needs_review" or resume.extracted_text is None:
        raise ValueError("Only successfully extracted resumes can be confirmed.")

    try:
        validate_confirmed_profile(candidate_data, resume.extracted_text)
    except UnsupportedEvidenceError:
        raise

    profile = session.get(CandidateProfile, DEMO_CANDIDATE_ID)
    if profile is None:
        profile = get_candidate_profile(session)
    for previous in session.scalars(
        select(ResumeVersion).where(
            ResumeVersion.candidate_profile_id == DEMO_CANDIDATE_ID,
            ResumeVersion.is_confirmed.is_(True),
        )
    ):
        previous.is_confirmed = False

    confirmed = candidate_data.model_dump(mode="json")
    profile.confirmed_profile = confirmed
    resume.confirmed_data = confirmed
    if candidate_data.full_name:
        profile.full_name = candidate_data.full_name.value
    profile.skills = _resume_profile_skills(candidate_data)
    profile.experience_years = (
        candidate_data.experience_years.value
        if candidate_data.experience_years
        else None
    )
    profile.preferred_roles = _clean_strings(
        [item.title.value for item in candidate_data.work_experience]
    )
    profile.categories = []
    profile.profile_source = "resume_confirmed"
    profile.is_configured = bool(
        profile.skills
        or profile.experience_years is not None
        or profile.preferred_roles
        or profile.locations
        or profile.work_modes
        or profile.employment_types
    )
    resume.is_confirmed = True
    resume.confirmed_at = datetime.now(timezone.utc)
    session.add_all([profile, resume])
    session.commit()
    session.refresh(resume)
    return _resume_payload(resume, message="Candidate-confirmed profile saved.")


def read_preferences(session: Session) -> CandidatePreferences:
    profile = get_candidate_profile(session)
    return CandidatePreferences(
        locations=profile.locations or [],
        work_modes=profile.work_modes or [],
        employment_types=profile.employment_types or [],
        salary_min=profile.salary_min,
        salary_max=profile.salary_max,
        salary_currency=profile.salary_currency or "USD",
    )


def update_preferences(
    session: Session, preferences: CandidatePreferences
) -> CandidatePreferences:
    profile = get_candidate_profile(session)
    profile.locations = _clean_strings(preferences.locations)
    profile.work_modes = _clean_strings(preferences.work_modes)
    profile.employment_types = _clean_strings(preferences.employment_types)
    profile.salary_min = preferences.salary_min
    profile.salary_max = preferences.salary_max
    profile.salary_currency = preferences.salary_currency.upper()
    profile.is_configured = bool(
        profile.skills
        or profile.experience_years is not None
        or profile.preferred_roles
        or profile.categories
        or profile.locations
        or profile.work_modes
        or profile.employment_types
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return read_preferences(session)
