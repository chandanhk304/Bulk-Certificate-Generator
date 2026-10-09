"""Job endpoints: submit a bulk request, check progress, list results, download all."""
from fastapi import APIRouter, BackgroundTasks, Query, Response

from app.dependencies import DbSession, Renderer, SessionFactory, Storage
from app.models import CertificateStatus
from app.schemas import CertificateOut, JobCreate, JobCreated, JobOut
from app.services import certificate_service, job_service
from app.services.processor import process_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=202, response_model=JobCreated)
def create_job(payload: JobCreate, background: BackgroundTasks, db: DbSession,
               session_factory: SessionFactory, renderer: Renderer, storage: Storage):
    """Accept a bulk request and return immediately; generation runs in the background."""
    job = job_service.create_job(db, payload)
    background.add_task(process_job, job.id, session_factory, renderer, storage)
    return JobCreated(
        job_id=job.id,
        status=job.status,
        total=job.total,
        accepted=job.total - job.failed,
        rejected=job.failed,
        status_url=f"/api/jobs/{job.id}",
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: DbSession):
    """Job status with success/failure counts and progress percentage."""
    return job_service.get_job(db, job_id)


@router.get("/{job_id}/certificates", response_model=list[CertificateOut])
def list_job_certificates(job_id: str, db: DbSession,
                          status: CertificateStatus | None = None,
                          limit: int = Query(100, ge=1, le=1000),
                          offset: int = Query(0, ge=0)):
    """Per-recipient results; filter with ?status=FAILED to see what went wrong."""
    return job_service.list_certificates(db, job_id, status, limit, offset)


@router.get("/{job_id}/download")
def download_job_archive(job_id: str, db: DbSession, storage: Storage):
    """ZIP containing every successfully generated certificate of the job."""
    content = certificate_service.build_job_archive(db, job_id, storage)
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="job_{job_id}.zip"'},
    )
