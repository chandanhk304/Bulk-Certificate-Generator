"""Job status and progress reporting."""
from app.models import JobStatus
from app.schemas import JobCreate, JobOut
from app.services import job_service
from tests.factories import job_payload, recipient


def test_new_job_is_pending_with_zero_progress(session_factory):
    # Call the service directly: via the API, TestClient would already have run the job.
    with session_factory() as db:
        job = job_service.create_job(db, JobCreate(**job_payload()))
        status = JobOut.model_validate(job)

    assert status.status == JobStatus.PENDING
    assert (status.pending, status.progress_percent) == (2, 0.0)


def test_finished_job_reports_completed_and_full_progress(client):
    job_id = client.post("/api/jobs", json=job_payload()).json()["job_id"]

    body = client.get(f"/api/jobs/{job_id}").json()
    assert body["status"] == "COMPLETED"
    assert (body["total"], body["succeeded"], body["failed"], body["pending"]) == (2, 2, 0, 0)
    assert body["progress_percent"] == 100.0
    assert body["completed_at"] is not None


def test_job_where_every_recipient_is_invalid_is_failed(client):
    job_id = client.post("/api/jobs", json=job_payload([{"name": "No Email"}])).json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "FAILED"


def test_validation_failures_count_towards_progress(client):
    recipients = [recipient("Good One"), {"name": "Bad", "email": "nope"}]
    job_id = client.post("/api/jobs", json=job_payload(recipients)).json()["job_id"]

    body = client.get(f"/api/jobs/{job_id}").json()
    assert body["status"] == "COMPLETED_WITH_ERRORS"
    assert (body["succeeded"], body["failed"]) == (1, 1)


def test_unknown_job_returns_404(client):
    assert client.get("/api/jobs/does-not-exist").status_code == 404
