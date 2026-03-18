# Document Ingestion Pipeline

Backend-only pipeline for uploading documents (PDF, images), storing them in S3, and asynchronously converting them to HTML via a scheduled management command. All conversion logic is **reimplemented in Veto** (no external or NDA-bound code).

## Flow

1. **Upload** – Client sends a file (multipart) to `POST /api/documents/upload/`. The backend validates type/size, generates a `job_id`, uploads the file to S3 under `documents_data/{job_id}/{filename}`, and creates an `IngestionDocument` row with `status=uploaded`. No synchronous conversion.

2. **Async processing** – A scheduled job (EventBridge → ECS task) runs `python manage.py process_document_ingestion` periodically. It selects rows with `status=uploaded`, downloads each file from S3, converts it to HTML (see Conversion below), uploads the HTML to `documents_data/{job_id}/{stem}.html`, and sets `output_html_s3_key` and `status=ready` (or `failed` on error).

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

## API summary

- `POST /api/documents/upload/` – Multipart: `file` (required), `patient` (required), optional `appointment`, `lab_order`, `document_type`. Returns 201 with `id`, `job_id`, `status`, `input_s3_key`.
- `GET /api/documents/` – List (clinic-scoped). Query params: `patient`, `status`.
- `GET /api/documents/{id}/` – Retrieve one (clinic-scoped).
- `POST /api/documents/{id}/download-url/` – Returns presigned URL for the HTML file (or input file if HTML not ready). Body: `{"url": "...", "expires_in": 3600}`.

Permissions: authenticated users with a clinic and staff/vet role (`IsStaffOrVet`, `HasClinic`).

## Terraform

- **Variables:** `documents_data_s3_bucket_name`, `documents_s3_region`, `documents_max_upload_mb`, `document_ingestion_schedule_expression` (default: `rate(10 minutes)`).
- **IAM:** ECS task role gets S3 `GetObject`/`PutObject` on `documents_data/*` and `ListBucket` on the bucket when the bucket name is set.
- **EventBridge:** Rule + ECS target to run `process_document_ingestion` on the schedule (only when bucket is configured).

## Tests

- **Upload** – Creates row and S3 key; S3 `upload_fileobj` is mocked.
- **Command** – Processes one document and sets `output_html_s3_key` and `status=ready`; S3 and conversion are mocked.
- **List/filters** – Clinic-scoped list and filter by `patient`.
- **Download URL** – Presigned URL returned for the document’s HTML (or input) key.

Run: `pytest backend/apps/documents/ -v`
