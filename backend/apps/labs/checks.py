"""Django system checks for lab integration configuration."""

from __future__ import annotations

from django.conf import settings
from django.core.checks import Warning, register


@register()
def lab_ingestion_s3_configuration(app_configs, **kwargs):
    """Warn when S3 mode requires a bucket but none is configured."""
    if not getattr(settings, "LAB_INGESTION_S3_ENABLED", True):
        return []
    if getattr(settings, "LAB_INGESTION_S3_MODE", "auto") != "always":
        return []
    dedicated = str(getattr(settings, "LAB_INGESTION_S3_BUCKET", "") or "").strip()
    shared = str(getattr(settings, "DOCUMENTS_DATA_S3_BUCKET", "") or "").strip()
    if dedicated or shared:
        return []
    return [
        Warning(
            "LAB_INGESTION_S3_MODE is 'always' but no S3 bucket is set "
            "(LAB_INGESTION_S3_BUCKET and DOCUMENTS_DATA_S3_BUCKET are empty). "
            "Ingest will fail when the pipeline tries to upload raw payloads.",
            hint="Set a bucket, use LAB_INGESTION_S3_MODE=auto or never, or disable with LAB_INGESTION_S3_ENABLED=false. "
            "See documentation/LAB_INTEGRATION.md",
            id="labs.W001",
        ),
    ]
