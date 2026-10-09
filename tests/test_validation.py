"""Input validation: request-level (reject with 422) vs recipient-level (record as FAILED)."""
import pytest

from app.config import settings
from tests.factories import job_payload, recipient


# ---------- Request-level: whole request rejected, no job created ----------

@pytest.mark.parametrize("payload", [
    job_payload(recipients=[]),                     # empty list
    job_payload(event_name=""),                     # blank event
    job_payload(event_name="   "),                  # whitespace-only event
    job_payload(issue_date="not-a-date"),           # bad date
    job_payload(recipients=["just a string"]),      # recipient isn't an object
    {"recipients": [recipient()]},                  # missing event_name
])
def test_malformed_request_is_rejected(client, payload):
    assert client.post("/api/jobs", json=payload).status_code == 422


def test_too_many_recipients_is_rejected(client):
    recipients = [recipient(f"P {i}") for i in range(settings.max_recipients_per_job + 1)]
    assert client.post("/api/jobs", json=job_payload(recipients)).status_code == 422


# ---------- Recipient-level: bad rows recorded, good rows still processed ----------

def test_invalid_recipients_are_recorded_as_failed(client):
    recipients = [
        recipient("Valid Person"),
        {"name": "", "email": "empty.name@example.com"},
        {"name": "Bad Email", "email": "not-an-email"},
        {"email": "missing.name@example.com"},
    ]
    body = client.post("/api/jobs", json=job_payload(recipients)).json()
    assert (body["accepted"], body["rejected"]) == (1, 3)

    failed = client.get(f"/api/jobs/{body['job_id']}/certificates", params={"status": "FAILED"}).json()
    errors = {c["position"]: c["error"] for c in failed}
    assert errors[1].startswith("name:")
    assert errors[2].startswith("email:")
    assert "name: Field required" in errors[3]


def test_duplicate_email_in_same_job_is_rejected(client):
    recipients = [recipient("Jane", "jane@example.com"), recipient("Jane Again", "JANE@example.com")]
    body = client.post("/api/jobs", json=job_payload(recipients)).json()

    assert (body["accepted"], body["rejected"]) == (1, 1)
    certs = client.get(f"/api/jobs/{body['job_id']}/certificates").json()
    assert certs[1]["error"] == "email: duplicate recipient in this job"


def test_whitespace_is_trimmed_from_names(client):
    body = client.post("/api/jobs", json=job_payload([recipient("  Jane Doe  ", "jane@example.com")])).json()
    cert = client.get(f"/api/jobs/{body['job_id']}/certificates").json()[0]
    assert cert["recipient_name"] == "Jane Doe"
