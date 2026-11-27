from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.schemas.health import (
    DependencyStatus,
    HealthResponse,
    ReadinessResponse,
    RootResponse,
)
from app.schemas.jobs import (
    CandidateProfileInput,
    CandidateProfileResponse,
    JobDetail,
    PicksResponse,
    RetrievalSearchResponse,
)
from app.schemas.resumes import (
    CandidatePreferences,
    ConfirmedCandidateProfile,
    ResumeDetail,
    ResumeListItem,
)
from app.services.discovery import (
    get_job_detail,
    get_job_picks,
    get_job_retrieval,
)
from app.services.profiles import get_candidate_profile, update_candidate_profile
from app.services.readiness import check_database, check_qdrant
from app.services.resume_pdf import OCRUnsupportedError, PDFValidationError
from app.services.resumes import (
    confirm_resume_profile,
    create_resume,
    get_resume,
    list_resumes,
    read_preferences,
    retry_resume_extraction,
    run_resume_extraction,
    update_preferences,
)
from app.services.resume_validation import UnsupportedEvidenceError

router = APIRouter()


@router.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(name=get_settings().app_name, status="ok")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
def ready() -> JSONResponse:
    dependencies = {
        "postgresql": DependencyStatus(
            status="available" if check_database() else "unavailable"
        ),
        "qdrant": DependencyStatus(
            status="available" if check_qdrant() else "unavailable"
        ),
    }
    is_ready = all(item.status == "available" for item in dependencies.values())
    response = ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        dependencies=dependencies,
    )
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content=response.model_dump(),
    )


@router.get(
    "/api/candidate",
    response_model=CandidateProfileResponse,
    tags=["candidate"],
)
def read_candidate_profile(
    session: Session = Depends(get_db),
) -> CandidateProfileResponse:
    return CandidateProfileResponse.model_validate(get_candidate_profile(session))


@router.put(
    "/api/candidate",
    response_model=CandidateProfileResponse,
    tags=["candidate"],
)
def save_candidate_profile(
    profile_data: CandidateProfileInput,
    session: Session = Depends(get_db),
) -> CandidateProfileResponse:
    return CandidateProfileResponse.model_validate(
        update_candidate_profile(session, profile_data)
    )


@router.get(
    "/api/jobs/picks",
    response_model=PicksResponse,
    tags=["jobs"],
)
def job_picks(
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db),
) -> PicksResponse:
    return get_job_picks(session, limit)


@router.get(
    "/api/jobs/retrieval/bm25",
    response_model=RetrievalSearchResponse,
    tags=["jobs"],
)
def bm25_job_retrieval(
    top_k: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_db),
) -> RetrievalSearchResponse:
    return get_job_retrieval(session, "bm25", top_k)


@router.get(
    "/api/jobs/retrieval/semantic",
    response_model=RetrievalSearchResponse,
    tags=["jobs"],
)
def semantic_job_retrieval(
    top_k: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_db),
) -> RetrievalSearchResponse:
    return get_job_retrieval(session, "semantic", top_k)


@router.get(
    "/api/jobs/retrieval/hybrid",
    response_model=RetrievalSearchResponse,
    tags=["jobs"],
)
def hybrid_job_retrieval(
    top_k: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_db),
) -> RetrievalSearchResponse:
    return get_job_retrieval(session, "hybrid", top_k)


@router.get(
    "/api/jobs/{job_id}",
    response_model=JobDetail,
    tags=["jobs"],
)
def job_detail(
    job_id: int,
    session: Session = Depends(get_db),
) -> JobDetail:
    result = get_job_detail(session, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return result


@router.get(
    "/api/preferences",
    response_model=CandidatePreferences,
    tags=["candidate"],
)
def candidate_preferences(
    session: Session = Depends(get_db),
) -> CandidatePreferences:
    return read_preferences(session)


@router.put(
    "/api/preferences",
    response_model=CandidatePreferences,
    tags=["candidate"],
)
def save_candidate_preferences(
    preferences: CandidatePreferences,
    session: Session = Depends(get_db),
) -> CandidatePreferences:
    return update_preferences(session, preferences)


@router.post(
    "/api/resumes",
    response_model=ResumeDetail,
    status_code=202,
    tags=["resumes"],
)
def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
) -> ResumeDetail:
    settings = get_settings()
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF resumes are supported.")
    if (file.content_type or "").split(";", 1)[0].strip().lower() != "application/pdf":
        raise HTTPException(
            status_code=415,
            detail="The uploaded file must have the application/pdf MIME type.",
        )
    content = file.file.read(settings.max_resume_size_bytes + 1)
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded PDF is empty.")
    if len(content) > settings.max_resume_size_bytes:
        raise HTTPException(status_code=413, detail="The PDF exceeds the upload size limit.")
    try:
        resume = create_resume(
            session,
            original_filename=filename,
            content_type="application/pdf",
            content=content,
        )
        if resume.extraction_status == "queued":
            background_tasks.add_task(run_resume_extraction, resume.id)
        return resume
    except OCRUnsupportedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PDFValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/api/resumes",
    response_model=list[ResumeListItem],
    tags=["resumes"],
)
def resumes(session: Session = Depends(get_db)) -> list[ResumeListItem]:
    return list_resumes(session)


@router.get(
    "/api/resumes/{resume_id}",
    response_model=ResumeDetail,
    tags=["resumes"],
)
def resume_detail(
    resume_id: int,
    session: Session = Depends(get_db),
) -> ResumeDetail:
    resume = get_resume(session, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    return resume


@router.post(
    "/api/resumes/{resume_id}/extract",
    response_model=ResumeDetail,
    status_code=202,
    tags=["resumes"],
)
def reprocess_resume(
    resume_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> ResumeDetail:
    try:
        resume = retry_resume_extraction(session, resume_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    background_tasks.add_task(run_resume_extraction, resume.id)
    return resume


@router.put(
    "/api/resumes/{resume_id}/confirm",
    response_model=ResumeDetail,
    tags=["resumes"],
)
def confirm_resume(
    resume_id: int,
    candidate_data: ConfirmedCandidateProfile,
    session: Session = Depends(get_db),
) -> ResumeDetail:
    try:
        resume = confirm_resume_profile(session, resume_id, candidate_data)
    except UnsupportedEvidenceError as exc:
        raise HTTPException(
            status_code=422,
            detail="A resume-sourced fact has missing or unsupported evidence. "
            "Correct its evidence or mark it as manually confirmed.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    return resume
