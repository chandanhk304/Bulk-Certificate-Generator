# Bulk Certificate Generator

A FastAPI backend that accepts a list of recipients in **one request**, generates a PDF certificate
for each valid recipient from a predefined template, tracks progress, and lets clients download
certificates individually or as a ZIP.

**Stack:** Python 3.11+ · FastAPI · SQLAlchemy 2 · SQLite · ReportLab · pytest

---

## 1. Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

No database setup is needed: SQLite is built into Python. The database file (`certificates.db`)
and its tables are created automatically on first start.

Optional: copy `.env.example` to `.env` to change the database URL, storage folder, or the maximum recipients per job.

## 2. Run the application

```bash
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Interactive docs (try every endpoint in the browser): http://localhost:8000/docs

## 3. Run the tests

```bash
pytest
```

| Requirement | Test file |
|---|---|
| Creating a generation job | `tests/test_create_job.py` |
| Input validation | `tests/test_validation.py` |
| Certificate generation | `tests/test_generation.py` |
| Job status / progress | `tests/test_status.py` |
| Individual certificate failure | `tests/test_partial_failure.py` |
| Retrieving certificates | `tests/test_retrieval.py` |

Each test uses its own temporary SQLite database and storage folder.

---

## 4. Submitting a certificate generation request

`POST /api/jobs`

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
        "event_name": "Python Bootcamp 2026",
        "issued_by": "Acme Academy",
        "issue_date": "2026-10-01",
        "recipients": [
          {"name": "Jane Doe",   "email": "jane@example.com"},
          {"name": "John Smith", "email": "john@example.com"},
          {"name": "Bad Row",    "email": "not-an-email"}
        ]
      }'
```

| Field | Rules |
|---|---|
| `event_name` | required, 1–150 chars |
| `issued_by` | optional, ≤ 100 chars |
| `issue_date` | optional `YYYY-MM-DD`, defaults to today |
| `recipients` | 1 – 1000 items; each needs `name` (1–100 chars) and a valid `email` |

Response: **202 Accepted** (generation continues in the background)

```json
{
  "job_id": "0cd1aee7-...",
  "status": "PENDING",
  "total": 3,
  "accepted": 2,
  "rejected": 1,
  "status_url": "/api/jobs/0cd1aee7-..."
}
```

### Check progress

`GET /api/jobs/{job_id}`

```json
{
  "id": "0cd1aee7-...",
  "status": "COMPLETED_WITH_ERRORS",
  "total": 3, "succeeded": 2, "failed": 1, "pending": 0,
  "progress_percent": 100.0,
  "completed_at": "2026-10-08T18:13:10"
}
```

Job statuses: `PENDING` → `PROCESSING` → `COMPLETED` | `COMPLETED_WITH_ERRORS` | `FAILED`.

### See per-recipient results

`GET /api/jobs/{job_id}/certificates?status=FAILED&limit=100&offset=0`

```json
[
  {
    "id": "…", "position": 2, "recipient_name": "Bad Row", "recipient_email": "not-an-email",
    "status": "FAILED",
    "error": "email: value is not a valid email address: An email address must have an @-sign.",
    "download_url": null
  }
]
```

`position` is the recipient's index in the original request, so each failure can be traced back to its input row.

## 5. Retrieving generated certificates

| Endpoint | Returns |
|---|---|
| `GET /api/jobs/{job_id}/certificates` | List with a `download_url` for each successful certificate |
| `GET /api/certificates/{id}` | Metadata for one certificate |
| `GET /api/certificates/{id}/download` | The PDF (`409` if pending or failed, `404` if unknown) |
| `GET /api/jobs/{job_id}/download` | ZIP of all successful certificates in the job |

```bash
curl -o cert.pdf http://localhost:8000/api/certificates/<certificate_id>/download
curl -o all.zip  http://localhost:8000/api/jobs/<job_id>/download
```

---

## 6. Design decisions

### Architecture

```
app/
  main.py            app factory, routers, error → HTTP mapping
  config.py          settings (env-overridable)
  database.py        engine, session factory, Base
  models.py          Job, Certificate tables + status enums
  schemas.py         Pydantic request/response models
  dependencies.py    picks concrete DB / renderer / storage (overridable)
  api/               thin HTTP layer (jobs.py, certificates.py)
  services/
    job_service.py          create job + per-recipient validation, queries
    processor.py            background generation loop
    renderer.py             CertificateRenderer interface + PDF template
    storage.py              FileStorage interface + local disk implementation
    certificate_service.py  file retrieval, ZIP building
    errors.py               domain errors (NotFound → 404, NotReady → 409)
```

- **Layered:** routes only handle HTTP, services hold the business logic, and models hold persistence. Routes contain no `try/except`; domain errors are mapped to status codes in one place (`main.py`).
- **Dependency inversion:** the processor depends on the `CertificateRenderer` and `FileStorage` *protocols*, not on ReportLab or the local disk. Concrete classes are chosen in `dependencies.py`. Tests swap them in through `app.dependency_overrides`, which is how the "one certificate fails" test injects a renderer that crashes for a specific recipient.

### Data model

- `jobs`: event information, status, and counters (`total`, `succeeded`, `failed`). The counters are stored on the job, so a status check is a single-row read instead of a `COUNT` over thousands of rows.
- `certificates`: one row per recipient with `position`, `status`, `error`, and `file_key`. The table has an index on `(job_id, status)` for the "pending" and "failed" queries.
- Files live in storage; the database stores only a **storage key** (`<id>.pdf`), not an absolute path. This keeps the database independent of where files are physically stored.

### Validation: two levels

1. **Request level (422, no job created):** missing or blank `event_name`, an invalid date, an empty recipient list, more than `MAX_RECIPIENTS_PER_JOB` recipients, or a recipient that isn't an object. These are mistakes in the request structure, so nothing is processed.
2. **Recipient level (the job is still created):** each recipient is validated individually. Invalid rows (blank name, bad or missing email, duplicate email within the job) are stored as `FAILED` with a readable `error`, while valid rows are generated. A typo in row 487 of 500 shouldn't force the client to resubmit everything.

### Bulk processing: background tasks

- `POST /api/jobs` validates the request, stores the job and its rows, and returns **202** right away. Generating hundreds of PDFs inside the HTTP request would risk timeouts.
- Generation runs with FastAPI `BackgroundTasks`, which calls `process_job(job_id, ...)`.
- **Failure isolation:** each certificate is rendered inside its own `try/except`. A failure marks only that row `FAILED` (with the reason), and the loop continues.
- **Live progress:** the processor commits after each certificate, so `GET /api/jobs/{id}` shows real-time progress. SQLite runs in WAL mode so these reads don't block on the writer.
- **Resumable:** the processor only picks up `PENDING` rows, so re-running a half-finished job continues where it stopped instead of duplicating work.

**Why not Celery or RQ?** They need a broker (such as Redis) and a separate worker process, which is unnecessary infrastructure for this scope. The trade-off is that `BackgroundTasks` runs inside the API process, so a server restart interrupts in-flight jobs. They remain `PENDING`/`PROCESSING` in the database and can be resumed because processing is idempotent. `process_job` is a plain function that receives only a job ID, so moving to Celery means changing **one line** in `api/jobs.py`, from `background.add_task(process_job, ...)` to `process_job_task.delay(job_id)`.

### Certificate template

The template is a single predefined layout drawn with ReportLab on landscape A4. It shows the recipient name, event, date, issuer, and a unique certificate ID for verification. Long names and event titles shrink automatically to fit. ReportLab is pure Python, so there are no system dependencies (unlike WeasyPrint or wkhtmltopdf).

## 7. Limitations and possible improvements

- **Restart recovery:** on startup, automatically resume jobs left in `PENDING`/`PROCESSING`.
- **Retry endpoint:** `POST /api/jobs/{id}/retry` could reset `FAILED` generation rows to `PENDING` and call `process_job` again.
- **Scale:** use Celery/RQ workers and PostgreSQL (only `DATABASE_URL` changes), store files in S3 (add an `S3FileStorage` class that implements `FileStorage`), and stream large ZIPs instead of building them in memory.
- **Unicode names:** the built-in Helvetica font covers Latin-1 characters only. Supporting scripts such as Devanagari or CJK requires registering a TTF font such as Noto Sans in `renderer.py`.
- **Schema migrations:** tables are created with `create_all`; a production system would use Alembic.
- **Authentication and rate limiting** are out of scope.
