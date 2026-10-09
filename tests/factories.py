"""Builders for request payloads used across tests."""


def recipient(name: str = "Jane Doe", email: str | None = None) -> dict:
    email = email or f"{name.lower().replace(' ', '.')}@example.com"
    return {"name": name, "email": email}


def job_payload(recipients: list[dict] | None = None, **overrides) -> dict:
    payload = {
        "event_name": "Python Bootcamp 2026",
        "issued_by": "Acme Academy",
        "issue_date": "2026-10-01",
        "recipients": recipients if recipients is not None else [recipient("Jane Doe"), recipient("John Smith")],
    }
    payload.update(overrides)
    return payload
