# Visit Recording + AI Summary (Frontend Integration)

This feature lets clinic staff upload a visit recording (audio/video), then retrieve AI-generated transcript and structured summary for that visit.

## High-level flow

1. FE uploads media file for an appointment.
2. Backend stores file in S3 and creates a `VisitRecording` row with `status=uploaded`.
3. Processing runs either:
   - inline on upload (`VISIT_RECORDINGS_PROCESS_INLINE_ON_UPLOAD=true`), or
   - asynchronously by command (`process_visit_recordings`) / scheduler.
4. Backend stores:
   - `transcript`,
   - `summary_structured`,
   - `summary_text`,
   - and updates `status` (`ready` or `failed`).
5. FE polls detail endpoint until terminal status.

## Endpoints

### 1) Upload recording

- `POST /api/visits/{appointment_id}/recordings/upload/`
- Auth: doctor/admin + clinic scope
- `multipart/form-data` with:
  - `file` (required): audio/video recording

Success response (`201`):

```json
{
  "id": 12,
  "job_id": "fa6d2624-3ac3-44cd-ae5e-ae1d9b9ecb62",
  "status": "uploaded",
  "input_s3_key": "visit_recordings/fa6d2624-3ac3-44cd-ae5e-ae1d9b9ecb62/visit.webm",
  "created_at": "2026-03-26T13:20:00.000000Z"
}
```

### 2) List recordings for appointment

- `GET /api/visits/{appointment_id}/recordings/`
- Returns array of recordings for this appointment (latest first).

### 3) Get recording detail (poll this)

- `GET /api/visit-recordings/{recording_id}/`

Important response fields:

- `status`: `uploaded` | `processing` | `ready` | `failed`
- `last_error`: present when failed
- `transcript`: full transcript when ready
- `summary_structured`: JSON sections for UI cards
- `summary_text`: plain formatted summary text
- `needs_review`: `true` when strict extraction had missing/non-grounded fields
- `unknown_fields`: fields set to `UNKNOWN` by strict guardrails

## FE polling contract

- Poll every 3-5 seconds after upload.
- Stop when `status` is `ready` or `failed`.
- If `failed`, show `last_error` and allow user to retry upload.

## Supported media

- Audio: `audio/webm`, `audio/ogg`, `audio/wav`, `audio/x-wav`, `audio/mpeg`
- Video: `video/webm`, `video/mp4`
- Max size: controlled by `VISIT_RECORDINGS_MAX_UPLOAD_MB` (default `200`)

## Notes for FE

- Use appointment id in upload/list URLs.
- Use returned `recording_id` for detail polling.
- Do not assume immediate `ready`; treat this as asynchronous processing.

## Strict AI mode (anti-hallucination)

Backend enforces strict extraction mode:

- model is instructed to return only direct quotes from transcript,
- missing information must be `UNKNOWN`,
- backend validates grounding against transcript and replaces non-grounded values with `UNKNOWN`,
- responses include `needs_review` + `unknown_fields` so FE can highlight sections requiring doctor verification.
