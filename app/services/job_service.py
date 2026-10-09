"""Job use-cases: create a job (with per-recipient validation) and query jobs/certificates."""
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Certificate, CertificateStatus, Job
from app.schemas import JobCreate, RecipientIn
from app.services.errors import NotFoundError


def create_job(db: Session, payload: JobCreate) -> Job:
    """Persist a job plus one certificate row per recipient.

    Valid recipients start as PENDING; invalid ones are stored as FAILED with the reason,
    so the client can see exactly which input rows were rejected and why.
    """
    certificates = _build_certificates(payload.recipients)
    rejected = sum(c.status == CertificateStatus.FAILED for c in certificates)

    job = Job(
        event_name=payload.event_name,
        issued_by=payload.issued_by,
        issue_date=payload.issue_date,
        total=len(certificates),
        succeeded=0,
        failed=rejected,
        certificates=certificates,
    )
    db.add(job)
    db.commit()
    return job


def get_job(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    return job


def list_certificates(db: Session, job_id: str, status: CertificateStatus | None = None,
                      limit: int = 100, offset: int = 0) -> list[Certificate]:
    """Certificates of a job in input order, optionally filtered by status."""
    get_job(db, job_id)  # 404 if the job doesn't exist
    query = select(Certificate).where(Certificate.job_id == job_id)
    if status is not None:
        query = query.where(Certificate.status == status)
    query = query.order_by(Certificate.position).limit(limit).offset(offset)
    return list(db.scalars(query))


# ---------- Validation helpers ----------


def _build_certificates(raw_recipients: list[dict[str, Any]]) -> list[Certificate]:
    seen_emails: set[str] = set()
    return [_validate_recipient(pos, raw, seen_emails) for pos, raw in enumerate(raw_recipients)]


def _validate_recipient(position: int, raw: dict[str, Any], seen_emails: set[str]) -> Certificate:
    """Turn one raw recipient into a Certificate row: PENDING if valid, FAILED (with reason) if not."""
    try:
        recipient = RecipientIn.model_validate(raw)
    except ValidationError as exc:
        return Certificate(
            position=position,
            recipient_name=_as_text(raw.get("name")),
            recipient_email=_as_text(raw.get("email")),
            status=CertificateStatus.FAILED,
            error=_format_errors(exc),
        )

    # Same person twice in one job is almost always a data mistake.
    email_key = recipient.email.lower()
    is_duplicate = email_key in seen_emails
    seen_emails.add(email_key)

    return Certificate(
        position=position,
        recipient_name=recipient.name,
        recipient_email=recipient.email,
        status=CertificateStatus.FAILED if is_duplicate else CertificateStatus.PENDING,
        error="email: duplicate recipient in this job" if is_duplicate else None,
    )


def _format_errors(exc: ValidationError) -> str:
    """Compact, human-readable message, e.g. 'name: String should have at least 1 character'."""
    parts = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err["loc"]) or "recipient"
        parts.append(f"{field}: {err['msg']}")
    return "; ".join(parts)


def _as_text(value: Any) -> str | None:
    """Best-effort string for storing invalid input (truncated to fit the column)."""
    return None if value is None else str(value)[:255]
