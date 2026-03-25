from __future__ import annotations

import json
import uuid
from urllib import error, request

from django.conf import settings


class VisitTranscriptionError(Exception):
    pass


def _build_multipart_form_data(
    *,
    fields: dict[str, str],
    file_field: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> tuple[bytes, str]:
    boundary = f"----veto-{uuid.uuid4().hex}"
    parts: list[bytes] = []

    for key, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
    )
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    return body, boundary


def transcribe_audio_with_whisper(*, audio_bytes: bytes, filename: str, content_type: str) -> str:
    api_key = str(getattr(settings, "OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise VisitTranscriptionError("OPENAI_API_KEY is not configured.")

    body, boundary = _build_multipart_form_data(
        fields={"model": "whisper-1"},
        file_field="file",
        filename=filename,
        content_type=content_type or "application/octet-stream",
        file_bytes=audio_bytes,
    )
    req = request.Request(
        url="https://api.openai.com/v1/audio/transcriptions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with request.urlopen(req, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise VisitTranscriptionError(f"Whisper request failed: {detail}") from exc
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise VisitTranscriptionError("Failed to transcribe audio with Whisper.") from exc

    transcript = str(payload.get("text", "")).strip()
    if not transcript:
        raise VisitTranscriptionError("Whisper returned empty transcript.")
    return transcript


def _extract_json_object(text: str) -> dict[str, str]:
    stripped = (text or "").strip()
    if not stripped:
        return {}
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            stripped = "\n".join(lines[1:-1]).strip()
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return {}
    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(k): str(v) for k, v in payload.items() if isinstance(k, str)}


def structure_transcript_with_claude(*, transcript: str) -> dict[str, str]:
    api_key = str(getattr(settings, "OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise VisitTranscriptionError("OPENAI_API_KEY is not configured.")

    schema_keys = [
        "anamnesis",
        "clinical_findings",
        "diagnosis",
        "treatment_plan",
        "owner_instructions",
    ]
    prompt = (
        "You are a veterinary assistant. Convert the transcript into JSON with keys exactly: "
        f"{', '.join(schema_keys)}. Keep concise factual text values. "
        "Return JSON only, no markdown, no extra keys.\n\n"
        f"Transcript:\n{transcript}"
    )
    req_body = json.dumps(
        {
            "model": "gpt-4o-mini",
            "max_tokens": 1200,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You output valid JSON only with keys: anamnesis, clinical_findings, "
                        "diagnosis, treatment_plan, owner_instructions."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
    ).encode("utf-8")
    req = request.Request(
        url="https://api.openai.com/v1/chat/completions",
        data=req_body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise VisitTranscriptionError(f"OpenAI structuring request failed: {detail}") from exc
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise VisitTranscriptionError("Failed to structure transcript with OpenAI.") from exc

    choices = payload.get("choices") or []
    content = ""
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        content = str(message.get("content", ""))
    structured = _extract_json_object(content)
    for key in schema_keys:
        structured.setdefault(key, "")
    return {key: str(structured.get(key, "")) for key in schema_keys}
