from __future__ import annotations

import json
import re
import uuid
from urllib import error, request

from django.conf import settings


class VisitTranscriptionError(Exception):
    pass


SUMMARY_SCHEMA_KEYS = [
    "anamnesis",
    "clinical_findings",
    "diagnosis",
    "treatment_plan",
    "owner_instructions",
]
SUMMARY_UNKNOWN = "UNKNOWN"


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


def _normalize_for_match(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"\s+", " ", lowered)
    lowered = re.sub(r"[^\w\s]", "", lowered)
    return lowered.strip()


def _split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<!\d)[.!?;]+(?!\d)|\n+", text)
    return [c.strip() for c in chunks if c.strip()]


def _is_grounded_quote(*, candidate: str, transcript: str) -> bool:
    candidate_norm = _normalize_for_match(candidate)
    transcript_norm = _normalize_for_match(transcript)
    return bool(candidate_norm) and candidate_norm in transcript_norm


def enforce_strict_summary(
    *, transcript: str, structured: dict[str, str]
) -> tuple[dict[str, str], bool]:
    strict: dict[str, str] = {}
    needs_review = False

    for key in SUMMARY_SCHEMA_KEYS:
        raw_value = str(structured.get(key, "")).strip()
        if not raw_value:
            strict[key] = SUMMARY_UNKNOWN
            needs_review = True
            continue
        if raw_value.upper() == SUMMARY_UNKNOWN:
            strict[key] = SUMMARY_UNKNOWN
            needs_review = True
            continue

        kept_sentences: list[str] = []
        for sentence in _split_sentences(raw_value):
            if _is_grounded_quote(candidate=sentence, transcript=transcript):
                kept_sentences.append(sentence)

        if not kept_sentences:
            strict[key] = SUMMARY_UNKNOWN
            needs_review = True
        else:
            strict[key] = ". ".join(kept_sentences).strip()

    return strict, needs_review


def structure_transcript_with_claude(*, transcript: str) -> dict[str, str]:
    api_key = str(getattr(settings, "OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise VisitTranscriptionError("OPENAI_API_KEY is not configured.")

    prompt = (
        "You are a strict extraction assistant for veterinary visits. "
        "Output JSON with keys exactly: "
        f"{', '.join(SUMMARY_SCHEMA_KEYS)}. "
        "For each key, copy exact quotes from the transcript only. "
        f"If the information is missing, set value to {SUMMARY_UNKNOWN}. "
        "Do not infer, generalize, or add medical assumptions. "
        "Return JSON only, no markdown, no extra keys.\n\n"
        f"Transcript:\n{transcript}"
    )
    req_body = json.dumps(
        {
            "model": "gpt-4o-mini",
            "max_tokens": 1200,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return valid JSON only. Allowed keys: anamnesis, clinical_findings, "
                        "diagnosis, treatment_plan, owner_instructions. "
                        "Values must be direct quotes from transcript or UNKNOWN."
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
    for key in SUMMARY_SCHEMA_KEYS:
        structured.setdefault(key, "")
    normalized = {key: str(structured.get(key, "")).strip() for key in SUMMARY_SCHEMA_KEYS}
    strict, _needs_review = enforce_strict_summary(transcript=transcript, structured=normalized)
    return strict
