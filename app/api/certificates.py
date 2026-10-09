"""Single-certificate endpoints: metadata and file download."""
from fastapi import APIRouter, Response

from app.dependencies import DbSession, Renderer, Storage
from app.schemas import CertificateOut
from app.services import certificate_service

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("/{certificate_id}", response_model=CertificateOut)
def get_certificate(certificate_id: str, db: DbSession):
    return certificate_service.get_certificate(db, certificate_id)


@router.get("/{certificate_id}/download")
def download_certificate(certificate_id: str, db: DbSession, storage: Storage, renderer: Renderer):
    """Download the generated file (409 if still pending or failed)."""
    certificate = certificate_service.get_certificate(db, certificate_id)
    content = certificate_service.read_certificate_file(certificate, storage)
    return Response(
        content=content,
        media_type=renderer.media_type,
        headers={"Content-Disposition":
                 f'attachment; filename="certificate_{certificate_id}.{renderer.file_extension}"'},
    )
