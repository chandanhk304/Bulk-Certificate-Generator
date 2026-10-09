"""Retrieving generated certificates: listing, single download, ZIP download."""
import io
import zipfile

from tests.factories import job_payload, recipient


def _create_job(client, recipients=None) -> str:
    return client.post("/api/jobs", json=job_payload(recipients)).json()["job_id"]


def test_list_certificates_includes_download_urls(client):
    job_id = _create_job(client)
    certs = client.get(f"/api/jobs/{job_id}/certificates").json()

    assert [c["recipient_name"] for c in certs] == ["Jane Doe", "John Smith"]
    assert certs[0]["download_url"] == f"/api/certificates/{certs[0]['id']}/download"


def test_list_certificates_supports_status_filter_and_pagination(client):
    job_id = _create_job(client, [recipient(f"Person {i}") for i in range(5)])

    page = client.get(f"/api/jobs/{job_id}/certificates", params={"limit": 2, "offset": 2}).json()
    assert [c["position"] for c in page] == [2, 3]
    assert client.get(f"/api/jobs/{job_id}/certificates", params={"status": "FAILED"}).json() == []


def test_download_single_certificate_returns_pdf(client):
    job_id = _create_job(client)
    cert_id = client.get(f"/api/jobs/{job_id}/certificates").json()[0]["id"]

    response = client.get(f"/api/certificates/{cert_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_get_certificate_metadata(client):
    job_id = _create_job(client)
    cert_id = client.get(f"/api/jobs/{job_id}/certificates").json()[0]["id"]

    body = client.get(f"/api/certificates/{cert_id}").json()
    assert (body["job_id"], body["status"]) == (job_id, "SUCCESS")


def test_download_job_zip_contains_only_successful_certificates(client):
    job_id = _create_job(client, [recipient("Jane Doe"), {"name": "Bad", "email": "x"}, recipient("John Smith")])

    response = client.get(f"/api/jobs/{job_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert len(names) == 2
    assert names[0].startswith("0001_Jane_Doe_") and names[1].startswith("0003_John_Smith_")


def test_zip_for_job_without_successes_returns_409(client):
    job_id = _create_job(client, [{"name": "Bad", "email": "x"}])
    assert client.get(f"/api/jobs/{job_id}/download").status_code == 409


def test_unknown_certificate_returns_404(client):
    assert client.get("/api/certificates/nope").status_code == 404
    assert client.get("/api/certificates/nope/download").status_code == 404
