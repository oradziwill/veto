# Document Ingestion Pipeline

Backend-only pipeline for uploading documents (PDF, images), storing them in S3, and asynchronously converting them to HTML via a scheduled management command. All conversion logic is **reimplemented in Veto** (no external or NDA-bound code).

## Flow

1. **Upload** – Client sends a file (multipart) to `POST /api/documents/upload/`. The backend validates type/size, generates a `job_id`, uploads the file to S3 under `documents_data/{job_id}/{filename}`, and creates an `IngestionDocument` row with `status=uploaded`. No synchronous conversion.

2. **Async processing** – A scheduled job (EventBridge → ECS task) runs `python manage.py process_document_ingestion` periodically. It selects rows with `status=uploaded`, downloads each file from S3, converts it to HTML (see Conversion below), uploads the HTML to `documents_data/{job_id}/{stem}.html`, and sets `output_html_s3_key` and `status=ready` (or `failed` on error). Failures store a short message in **`last_error`** for support and UI.

3. **List / retrieve / download** – Authenticated clinic staff can list documents (with filters e.g. `patient`, `status`), retrieve metadata with `GET /api/documents/{id}/`, and obtain a presigned URL for the HTML (or original file) via `POST /api/documents/{id}/download-url/`.

All input and output live in a **single S3 bucket** under the prefix `documents_data/{job_id}/`.

## Environment variables

| Variable | Description |
|---------|-------------|
| `DOCUMENTS_DATA_S3_BUCKET` | S3 bucket name for ingestion (input and output). Empty = feature disabled. |
| `DOCUMENTS_S3_REGION` | AWS region for the bucket (default: `us-east-1`). |
| `DOCUMENTS_MAX_UPLOAD_MB` | Max upload size in MB (default: `50`). |

In production these are passed via ECS task definition (Terraform variables: `documents_data_s3_bucket_name`, `documents_s3_region`, `documents_max_upload_mb`).

## Conversion (reimplemented in Veto)

- **PDF** – PyMuPDF (`fitz`) extracts text. If extracted text is minimal (below a threshold), pages are rendered to images and sent to **OpenAI vision** (gpt-4o-mini) for OCR; results are combined and normalized to HTML.
- **Images** (JPEG, PNG, GIF, WebP) – Single image is sent to OpenAI vision for text extraction and normalized to HTML.

Output is minimal HTML (e.g. `<html><body><p>...</p></body></html>`). Optional `metadata.json` under `documents_data/{job_id}/` is not written in the current implementation.

**Dependencies:** `pymupdf`, `openai` (and `boto3` for S3). OCR requires `OPENAI_API_KEY` to be set when processing low-text PDFs or images.

## Frontend integration (async flow + polling)

Conversion runs **asynchronously** in the backend (scheduled job). The frontend should not wait for conversion on upload.

1. **Upload** – `POST /api/documents/upload/` with `file` + `patient`. Response is **immediate** (201) with `id`, `job_id`, `status: "uploaded"`. No conversion happens in this request.
2. **Poll for completion** – Use `GET /api/documents/{id}/` (or `GET /api/documents/?patient=…`) and check `status`:
   - `uploaded` → waiting for processing
   - `processing` → conversion in progress
   - `ready` → HTML is available; use download-url to get it
   - `failed` → conversion failed; show **`last_error`**, no HTML
3. **Get HTML for display** – When `status === "ready"`, call `POST /api/documents/{id}/download-url/`. Use the returned `url` (presigned, valid for `expires_in` seconds) to fetch the HTML in the browser (e.g. in an iframe or by fetching and rendering).

Polling interval suggestion: every 5–10 seconds until `ready` or `failed`, with a timeout (e.g. 5 minutes).

## API summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/upload/` | Multipart: `file` (required), `patient` (required). Optional: `appointment`, `lab_order`, `document_type`. Returns 201: `{ id, job_id, status, input_s3_key, created_at }`. |
| GET | `/api/documents/` | List (clinic-scoped). Query: `patient`, `status`. Returns list of documents with full metadata. |
| GET | `/api/documents/{id}/` | Retrieve one. Returns full document (including `status`, `last_error`, `output_html_s3_key` when ready). |
| POST | `/api/documents/{id}/download-url/` | Returns `{ url, expires_in }` – use `url` to load the HTML (or original file if not ready). |

Permissions: authenticated users with a clinic and staff/vet role (`IsStaffOrVet`, `HasClinic`).

## Terraform

- **Variables:** `documents_data_s3_bucket_name`, `documents_s3_region`, `documents_max_upload_mb`, `document_ingestion_schedule_expression` (default: `rate(10 minutes)`).
- **IAM:** ECS task role gets S3 `GetObject`/`PutObject` on `documents_data/*` and `ListBucket` on the bucket when the bucket name is set.
- **EventBridge:** Rule + ECS target to run `process_document_ingestion` on the schedule (only when bucket is configured).

## CI: post-deploy smoke checks (dev)

When the **dev** ECS stack is scaled down, the ALB may return **503** and the deploy workflow smoke step fails. For repository **`dev`** deploys, smoke checks are **skipped by default**. To run them (e.g. when dev is kept online), set GitHub repository variable **`ENABLE_DEV_POST_DEPLOY_SMOKE`** to `true`. **Prod** always runs smoke checks.

## Stuck `processing` rows

If a worker dies after setting `status=processing`, the row can stay stuck. Inspect with Django admin or SQL, then either:

- **Dry run** (list candidates):
  `python manage.py release_stuck_document_processing --max-age-minutes 30`
- **Retry** (set back to `uploaded` so the batch command picks them up):
  `python manage.py release_stuck_document_processing --max-age-minutes 30 --apply`
- **Give up** (mark `failed` with an explanatory `last_error`):
  `python manage.py release_stuck_document_processing --max-age-minutes 30 --apply --to-failed`

Single-document processing is also supported:
`python manage.py process_document_ingestion --doc-id <id>`

## Tests

- **Upload** – Creates row and S3 key; S3 `upload_fileobj` is mocked.
- **Command** – Processes one document and sets `output_html_s3_key` and `status=ready`; S3 and conversion are mocked.
- **List/filters** – Clinic-scoped list and filter by `patient`.
- **Download URL** – Presigned URL returned for the document’s HTML (or input) key.

Run: `pytest backend/apps/documents/ -v`
