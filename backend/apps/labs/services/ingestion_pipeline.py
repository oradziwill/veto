from __future__ import annotations

import hashlib
import secrets

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.labs.integrations.json_payload import IngestJsonError, parse_json_payload
from apps.labs.models import (
    LabIngestionEnvelope,
    LabIntegrationDevice,
    LabObservation,
    LabOrder,
    LabOrderLine,
)
from apps.labs.services.identifier_resolution import resolve_order_from_identifiers
from apps.labs.services.lab_ingestion_storage import (
    download_raw_bytes,
    should_store_raw_on_s3,
    upload_raw_bytes,
)
from apps.labs.services.mapping import resolve_internal_test
from apps.labs.services.materialization import (
    materialize_lab_order,
    refresh_order_status_after_integration,
)


class IngestionTransientError(Exception):
    """Raise for retryable failures (future Celery)."""


def build_idempotency_key(*, clinic_id: int, device_id: int | None, raw: bytes) -> str:
    digest = hashlib.sha256(raw).hexdigest()
    return f"api:{clinic_id}:{device_id or 'na'}:{digest}"


def create_envelope_and_process(
    *,
    clinic_id: int,
    device: LabIntegrationDevice,
    raw_bytes: bytes,
    source_type: str = LabIngestionEnvelope.SourceType.API,
) -> tuple[LabIngestionEnvelope, bool]:
    """
    Create envelope if new idempotency key; run pipeline synchronously.
    Returns (envelope, created).
    """
    key = build_idempotency_key(clinic_id=clinic_id, device_id=device.id, raw=raw_bytes)
    existing = LabIngestionEnvelope.objects.filter(clinic_id=clinic_id, idempotency_key=key).first()
    if existing:
        return existing, False

    use_s3 = should_store_raw_on_s3(len(raw_bytes))
    try:
        with transaction.atomic():
            env = LabIngestionEnvelope(
                clinic_id=clinic_id,
                device=device,
                idempotency_key=key,
                source_type=source_type,
                raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),
                processing_status=LabIngestionEnvelope.ProcessingStatus.RECEIVED,
                raw_body_text="",
            )
            env.save()
            if use_s3:
                bucket, s3_key = upload_raw_bytes(
                    clinic_id=clinic_id,
                    envelope_id=env.id,
                    body=raw_bytes,
                )
                env.raw_s3_bucket = bucket
                env.raw_s3_key = s3_key
                env.save(update_fields=["raw_s3_bucket", "raw_s3_key"])
            else:
                env.raw_body_text = raw_bytes.decode("utf-8", errors="replace")
                env.save(update_fields=["raw_body_text"])
    except IntegrityError:
        dup = LabIngestionEnvelope.objects.filter(
            clinic_id=clinic_id,
            idempotency_key=key,
        ).first()
        if dup:
            return dup, False
        raise
    env.refresh_from_db()
    process_lab_ingestion_envelope(env.id)
    return env, True


@transaction.atomic
def process_lab_ingestion_envelope(envelope_id: int) -> None:
    env = (
        LabIngestionEnvelope.objects.select_for_update()
        .filter(pk=envelope_id)
        .select_related("device", "clinic")
        .first()
    )
    if not env:
        return

    env.processing_status = LabIngestionEnvelope.ProcessingStatus.PARSING
    env.error_code = ""
    env.error_detail = ""
    env.save(update_fields=["processing_status", "error_code", "error_detail"])

    raw = b""
    try:
        if (env.raw_s3_bucket or "").strip() and (env.raw_s3_key or "").strip():
            raw = download_raw_bytes(bucket=env.raw_s3_bucket.strip(), key=env.raw_s3_key.strip())
        elif env.raw_file:
            try:
                env.raw_file.open("rb")
                raw = env.raw_file.read()
            finally:
                env.raw_file.close()
        elif env.raw_body_text:
            raw = env.raw_body_text.encode("utf-8")
    except Exception as e:
        env.processing_status = LabIngestionEnvelope.ProcessingStatus.ERROR
        env.error_code = "E_RAW_LOAD"
        env.error_detail = str(e)[:500]
        env.save(update_fields=["processing_status", "error_code", "error_detail"])
        return

    try:
        parsed = parse_json_payload(raw)
    except IngestJsonError as e:
        env.processing_status = LabIngestionEnvelope.ProcessingStatus.REJECTED
        env.error_code = "E_PARSE"
        env.error_detail = str(e)[:500]
        env.save(update_fields=["processing_status", "error_code", "error_detail", "parsed_at"])
        return

    env.payload_metadata = {**env.payload_metadata, **parsed.metadata}
    env.processing_status = LabIngestionEnvelope.ProcessingStatus.PARSED
    env.parsed_at = timezone.now()
    env.save(update_fields=["payload_metadata", "processing_status", "parsed_at"])

    device = env.device
    order, sample = resolve_order_from_identifiers(env.clinic_id, parsed.identifiers)

    env.processing_status = LabIngestionEnvelope.ProcessingStatus.MAPPING
    env.save(update_fields=["processing_status"])

    LabObservation.objects.filter(envelope=env).delete()

    order_ids: set[int] = set()
    for draft in parsed.observations:
        internal = resolve_internal_test(
            clinic_id=env.clinic_id,
            device=device,
            vendor_code=draft.vendor_code,
        )
        line = None
        match_status = LabObservation.MatchStatus.UNMATCHED
        if order and internal:
            line = LabOrderLine.objects.filter(order=order, test=internal).first()
            if line:
                match_status = LabObservation.MatchStatus.MATCHED
            else:
                match_status = LabObservation.MatchStatus.UNMATCHED
        elif order and not internal:
            match_status = LabObservation.MatchStatus.AMBIGUOUS

        LabObservation.objects.create(
            clinic_id=env.clinic_id,
            envelope=env,
            device=device,
            lab_order=order,
            lab_order_line=line,
            sample=sample,
            match_status=match_status,
            vendor_test_code=draft.vendor_code,
            vendor_test_name=draft.vendor_name,
            internal_test=internal,
            value_text=draft.value_text,
            value_numeric=draft.value_numeric,
            unit=draft.unit,
            ref_low=draft.ref_low,
            ref_high=draft.ref_high,
            abnormal_flag=draft.abnormal_flag,
            result_status=draft.result_status,
            natural_key=draft.natural_key,
            observed_at=draft.observed_at,
        )
        if order:
            order_ids.add(order.id)

    env.processing_status = LabIngestionEnvelope.ProcessingStatus.ATTACHING
    env.save(update_fields=["processing_status"])

    for oid in order_ids:
        order = LabOrder.objects.get(pk=oid)
        materialize_lab_order(order)
        refresh_order_status_after_integration(order)

    env.processing_status = LabIngestionEnvelope.ProcessingStatus.COMPLETED
    env.save(update_fields=["processing_status"])


def verify_ingest_token(device: LabIntegrationDevice, token: str | None) -> bool:
    expected = (device.ingest_token or "").strip()
    if not expected:
        return False
    if token is None:
        return False
    return secrets.compare_digest(expected, token)
