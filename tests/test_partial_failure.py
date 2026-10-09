"""A failure generating one certificate must not stop the others."""
import pytest

from app.dependencies import get_renderer
from app.main import app
from app.services.renderer import CertificateData, PdfCertificateRenderer
from tests.factories import job_payload, recipient


class FlakyRenderer(PdfCertificateRenderer):
    """Real renderer that crashes for one specific recipient."""

    def render(self, data: CertificateData) -> bytes:
        if data.recipient_name == "Crash Test":
            raise RuntimeError("font engine exploded")
        return super().render(data)


@pytest.fixture
def flaky_client(client):
    app.dependency_overrides[get_renderer] = lambda: FlakyRenderer()
    return client


def test_one_generation_failure_does_not_block_others(flaky_client):
    recipients = [recipient("Alice"), recipient("Crash Test"), recipient("Bob")]
    job_id = flaky_client.post("/api/jobs", json=job_payload(recipients)).json()["job_id"]

    job = flaky_client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED_WITH_ERRORS"
    assert (job["succeeded"], job["failed"]) == (2, 1)

    certs = flaky_client.get(f"/api/jobs/{job_id}/certificates").json()
    assert [c["status"] for c in certs] == ["SUCCESS", "FAILED", "SUCCESS"]
    assert certs[1]["error"] == "generation: font engine exploded"
    assert certs[1]["download_url"] is None


def test_failed_certificate_cannot_be_downloaded(flaky_client):
    job_id = flaky_client.post("/api/jobs", json=job_payload([recipient("Crash Test")])).json()["job_id"]
    cert = flaky_client.get(f"/api/jobs/{job_id}/certificates").json()[0]

    assert flaky_client.get(f"/api/jobs/{job_id}").json()["status"] == "FAILED"
    assert flaky_client.get(f"/api/certificates/{cert['id']}/download").status_code == 409
