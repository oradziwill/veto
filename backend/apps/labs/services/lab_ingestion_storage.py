"""S3 storage for lab ingest raw payloads (boto3; same pattern as documents / visit recordings)."""

from __future__ import annotations

import logging

import boto3
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


def get_lab_ingestion_bucket() -> str:
    if not getattr(settings, "LAB_INGESTION_S3_ENABLED", True):
        return ""
    dedicated = str(getattr(settings, "LAB_INGESTION_S3_BUCKET", "") or "").strip()
    if dedicated:
        return dedicated
    return str(getattr(settings, "DOCUMENTS_DATA_S3_BUCKET", "") or "").strip()


def _get_s3_client():
    region = getattr(settings, "LAB_INGESTION_S3_REGION", None) or getattr(
        settings, "DOCUMENTS_S3_REGION", "us-east-1"
    )
    return boto3.client("s3", region_name=region)


def should_store_raw_on_s3(raw_len: int) -> bool:
    if not get_lab_ingestion_bucket():
        return False
    mode = getattr(settings, "LAB_INGESTION_S3_MODE", "auto")
    if mode == "always":
        return True
    if mode == "never":
        return False
    max_inline = int(getattr(settings, "LAB_INGESTION_RAW_INLINE_MAX_BYTES", 512 * 1024))
    return raw_len > max_inline


def build_s3_key(*, clinic_id: int, envelope_id: int) -> str:
    prefix = (
        str(getattr(settings, "LAB_INGESTION_S3_PREFIX", "lab-ingestion") or "lab-ingestion")
        .strip()
        .strip("/")
    )
    return f"{prefix}/clinic_{clinic_id}/envelope_{envelope_id}.bin"


def upload_raw_bytes(*, clinic_id: int, envelope_id: int, body: bytes) -> tuple[str, str]:
    bucket = get_lab_ingestion_bucket()
    if not bucket:
        raise ValueError("Lab ingestion S3 bucket is not configured")
    key = build_s3_key(clinic_id=clinic_id, envelope_id=envelope_id)
    client = _get_s3_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/octet-stream",
        ServerSideEncryption="AES256",
    )
    logger.info(
        "Lab ingest raw uploaded to S3 clinic_id=%s envelope_id=%s key=%s",
        clinic_id,
        envelope_id,
        key,
    )
    return bucket, key


def download_raw_bytes(*, bucket: str, key: str) -> bytes:
    client = _get_s3_client()
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()
    except ClientError as e:
        logger.warning("Lab ingest S3 download failed bucket=%s key=%s error=%s", bucket, key, e)
        raise
