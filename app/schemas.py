"""Pydantic schemas: request validation and response shapes."""
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field

from app.config import settings
from app.models import CertificateStatus, JobStatus

# ---------- Requests ----------


class RecipientIn(BaseModel):
    """One recipient. Validated item-by-item so one bad row doesn't reject the whole job."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr


class JobCreate(BaseModel):
    """Bulk generation request. Problems at this level -> 422 and no job is created."""

    model_config = ConfigDict(str_strip_whitespace=True)

    event_name: str = Field(min_length=1, max_length=150)
    issued_by: str = Field(default="", max_length=100)
    issue_date: date = Field(default_factory=date.today)
    # Raw dicts on purpose: each one is validated separately against RecipientIn.
    recipients: list[dict[str, Any]] = Field(
        min_length=1, max_length=settings.max_recipients_per_job
    )


# ---------- Responses ----------


class JobCreated(BaseModel):
    job_id: str
    status: JobStatus
    total: int
    accepted: int   # passed validation, queued for generation
    rejected: int   # failed validation, recorded as FAILED certificates
    status_url: str


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_name: str
    issued_by: str
    issue_date: date
    status: JobStatus
    total: int
    succeeded: int
    failed: int
    created_at: datetime
    completed_at: datetime | None

    @computed_field
    @property
    def pending(self) -> int:
        return self.total - self.succeeded - self.failed

    @computed_field
    @property
    def progress_percent(self) -> float:
        if self.total == 0:
            return 100.0
        return round(100 * (self.succeeded + self.failed) / self.total, 1)


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    position: int
    recipient_name: str | None
    recipient_email: str | None
    status: CertificateStatus
    error: str | None
    generated_at: datetime | None

    @computed_field
    @property
    def download_url(self) -> str | None:
        if self.status != CertificateStatus.SUCCESS:
            return None
        return f"/api/certificates/{self.id}/download"
