"""Creating a generation job."""
from app.models import Certificate, Job
from tests.factories import job_payload, recipient


def test_create_job_returns_202_with_job_reference(client):
    response = client.post("/api/jobs", json=job_payload())

    assert response.status_code == 202
    body = response.json()
    assert body["total"] == 2
    assert body["accepted"] == 2
    assert body["rejected"] == 0
    assert body["status_url"] == f"/api/jobs/{body['job_id']}"


def test_create_job_persists_one_certificate_per_recipient(client, session_factory):
    recipients = [recipient(f"Person {i}") for i in range(25)]
    job_id = client.post("/api/jobs", json=job_payload(recipients)).json()["job_id"]

    with session_factory() as db:
        job = db.get(Job, job_id)
        assert job.event_name == "Python Bootcamp 2026"
        assert db.query(Certificate).filter_by(job_id=job_id).count() == 25
