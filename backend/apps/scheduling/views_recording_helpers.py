from __future__ import annotations

import json
import re

import boto3
from django.conf import settings


def _safe_s3_filename(original: str) -> str:
    name = original or "recording"
    stem, dot, suffix = name.rpartition(".")
    if not dot:
        stem = name
        suffix = ""
    safe_stem = re.sub(r"[^\w\-.]", "_", stem)[:200]
    safe_suffix = re.sub(r"[^\w]", "", suffix)[:10]
    return (safe_stem or "recording") + (f".{safe_suffix}" if safe_suffix else "")


def _get_recording_s3_client():
    region = getattr(settings, "VISIT_RECORDINGS_S3_REGION", "") or getattr(
        settings, "DOCUMENTS_S3_REGION", "us-east-1"
    )
    return boto3.client("s3", region_name=region)


def _get_eventbridge_client():
    region = getattr(settings, "VISIT_RECORDINGS_S3_REGION", "") or getattr(
        settings, "DOCUMENTS_S3_REGION", "us-east-1"
    )
    return boto3.client("events", region_name=region)


def _trigger_visit_recording_uploaded(recording_id: int) -> None:
    detail = json.dumps({"visit_recording_id": int(recording_id)})
    _get_eventbridge_client().put_events(
        Entries=[
            {
                "Source": "veto.scheduling",
                "DetailType": "visit_recording_uploaded",
                "Detail": detail,
            }
        ]
    )
