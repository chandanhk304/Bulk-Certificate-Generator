"""Background job processing: generates every PENDING certificate of a job.

`process_job` only needs a job id plus its collaborators, so the same function can be
called from FastAPI BackgroundTasks today or a Celery/RQ worker later.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Certificate, CertificateStatus, Job, JobStatus, utcnow
from app.services.renderer import CertificateData, CertificateRenderer
from app.services.storage import FileStorage

logger = logging.getLogger(__name__)


def process_job(job_id: str, session_factory: sessionmaker,
                renderer: CertificateRenderer, storage: FileStorage) -> None:
    """Generate all pending certificates; one failure never stops the others.

    Only PENDING rows are processed, so re-running a half-finished job safely resumes it.
    """
    # Background tasks outlive the request, so they open their own DB session.
    with session_factory() as db:
        job = db.get(Job, job_id)
        if job is None:
            logger.error("Job %s not found, nothing to process", job_id)
            return

        try:
            job.status = JobStatus.PROCESSING
            db.commit()

            pending = db.scalars(
                select(Certificate)
                .where(Certificate.job_id == job_id, Certificate.status == CertificateStatus.PENDING)
                .order_by(Certificate.position)
            ).all()
            for certificate in pending:
                _generate_one(db, job, certificate, renderer, storage)

            job.status = _final_status(job)
        except Exception:
            # Unexpected infrastructure error (e.g. DB down): mark the whole job failed.
            logger.exception("Job %s crashed", job_id)
            db.rollback()
            job.status = JobStatus.FAILED

        job.completed_at = utcnow()
        db.commit()
        logger.info("Job %s finished: %s (%d ok, %d failed)",
                    job_id, job.status, job.succeeded, job.failed)


def _generate_one(db: Session, job: Job, certificate: Certificate,
                  renderer: CertificateRenderer, storage: FileStorage) -> None:
    """Render and store one certificate, recording success or the failure reason."""
    try:
        content = renderer.render(CertificateData(
            certificate_id=certificate.id,
            recipient_name=certificate.recipient_name,
            event_name=job.event_name,
            issue_date=job.issue_date,
            issued_by=job.issued_by,
        ))
        file_key = f"{certificate.id}.{renderer.file_extension}"
        storage.save(file_key, content)

        certificate.file_key = file_key
        certificate.status = CertificateStatus.SUCCESS
        certificate.generated_at = utcnow()
        job.succeeded += 1
    except Exception as exc:
        logger.warning("Certificate %s failed: %s", certificate.id, exc)
        certificate.status = CertificateStatus.FAILED
        certificate.error = f"generation: {exc}"
        job.failed += 1

    # Commit per certificate so progress is visible to status polling in real time.
    db.commit()


def _final_status(job: Job) -> JobStatus:
    if job.failed == 0:
        return JobStatus.COMPLETED
    if job.succeeded == 0:
        return JobStatus.FAILED
    return JobStatus.COMPLETED_WITH_ERRORS
