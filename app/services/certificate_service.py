"""Certificate retrieval: single files and a ZIP of a whole job."""
import io
import re
import zipfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Certificate, CertificateStatus
from app.services.errors import NotFoundError, NotReadyError
from app.services.job_service import get_job
from app.services.storage import FileStorage


def get_certificate(db: Session, certificate_id: str) -> Certificate:
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise NotFoundError(f"Certificate {certificate_id} not found")
    return certificate


def read_certificate_file(certificate: Certificate, storage: FileStorage) -> bytes:
    """Return the generated file; only SUCCESS certificates have one."""
    if certificate.status != CertificateStatus.SUCCESS or not certificate.file_key:
        raise NotReadyError(f"Certificate {certificate.id} is {certificate.status}, no file available")
    try:
        return storage.read(certificate.file_key)
    except FileNotFoundError:
        raise NotFoundError(f"File for certificate {certificate.id} is missing from storage")


def build_job_archive(db: Session, job_id: str, storage: FileStorage) -> bytes:
    """ZIP every successfully generated certificate of a job (built in memory)."""
    get_job(db, job_id)
    certificates = db.scalars(
        select(Certificate)
        .where(Certificate.job_id == job_id, Certificate.status == CertificateStatus.SUCCESS)
        .order_by(Certificate.position)
    ).all()
    if not certificates:
        raise NotReadyError(f"Job {job_id} has no generated certificates yet")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for cert in certificates:
            archive.writestr(_archive_name(cert), storage.read(cert.file_key))
    return buffer.getvalue()


def _archive_name(cert: Certificate) -> str:
    """Readable, unique file name, e.g. '0001_Jane_Doe_3f2a9c1b.pdf'."""
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", cert.recipient_name or "").strip("_") or "recipient"
    extension = cert.file_key.rsplit(".", 1)[-1]
    return f"{cert.position + 1:04d}_{safe_name}_{cert.id[:8]}.{extension}"
