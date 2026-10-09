"""Certificate generation: the PDF template renderer and files produced by a job."""
from datetime import date

from app.services.renderer import CertificateData, PdfCertificateRenderer
from tests.factories import job_payload


def _data(**overrides) -> CertificateData:
    fields = dict(certificate_id="abc-123", recipient_name="Jane Doe",
                  event_name="Python Bootcamp", issue_date=date(2026, 10, 1), issued_by="Acme")
    fields.update(overrides)
    return CertificateData(**fields)


def test_renderer_produces_a_pdf():
    content = PdfCertificateRenderer().render(_data())
    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_renderer_embeds_recipient_specific_title():
    # Document title includes the recipient's name (stored uncompressed in PDF metadata).
    content = PdfCertificateRenderer().render(_data(recipient_name="Ada Lovelace"))
    assert b"Ada Lovelace" in content


def test_renderer_handles_very_long_names():
    content = PdfCertificateRenderer().render(_data(recipient_name="X" * 100))
    assert content.startswith(b"%PDF")


def test_job_generates_a_file_per_valid_recipient(client, storage):
    job_id = client.post("/api/jobs", json=job_payload()).json()["job_id"]

    certs = client.get(f"/api/jobs/{job_id}/certificates").json()
    assert all(c["status"] == "SUCCESS" for c in certs)
    for cert in certs:
        assert storage.read(f"{cert['id']}.pdf").startswith(b"%PDF")
