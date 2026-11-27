from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Job Intelligence Platform API"
    database_url: str = "postgresql+psycopg://127.0.0.1:5433/job_intelligence"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    resume_processing_stale_seconds: int = Field(default=600, ge=300, le=7200)
    resume_storage_dir: Path = PROJECT_ROOT / "storage" / "resumes"
    max_resume_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    max_resume_pages: int = Field(default=50, ge=1, le=200)
    max_resume_text_chars: int = Field(default=120_000, ge=1000)
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    match_weight_required_skills: float = Field(default=0.30, ge=0, le=1)
    match_weight_preferred_skills: float = Field(default=0.15, ge=0, le=1)
    match_weight_experience: float = Field(default=0.15, ge=0, le=1)
    match_weight_role: float = Field(default=0.15, ge=0, le=1)
    match_weight_location: float = Field(default=0.10, ge=0, le=1)
    match_weight_work_mode: float = Field(default=0.075, ge=0, le=1)
    match_weight_employment_type: float = Field(default=0.075, ge=0, le=1)

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_matching_weights(self) -> Settings:
        weights = (
            self.match_weight_required_skills,
            self.match_weight_preferred_skills,
            self.match_weight_experience,
            self.match_weight_role,
            self.match_weight_location,
            self.match_weight_work_mode,
            self.match_weight_employment_type,
        )
        if not any(weights):
            raise ValueError("At least one matching score weight must be greater than zero.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
