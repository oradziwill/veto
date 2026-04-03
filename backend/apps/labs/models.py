"""
Lab integration: in-clinic and external labs, orders, results.
"""

from django.conf import settings
from django.db import models

from apps.patients.models import Patient
from apps.scheduling.models import Appointment, HospitalStay
from apps.tenancy.models import Clinic


class Lab(models.Model):
    """Lab provider - in-clinic or external."""

    class LabType(models.TextChoices):
        IN_CLINIC = "in_clinic", "In-Clinic"
        EXTERNAL = "external", "External"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="labs",
        null=True,
        blank=True,
        help_text="Null for external labs used by multiple clinics",
    )
    name = models.CharField(max_length=255)
    lab_type = models.CharField(
        max_length=20,
        choices=LabType.choices,
        default=LabType.IN_CLINIC,
    )
    address = models.CharField(max_length=512, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["clinic"]), models.Index(fields=["lab_type"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_lab_type_display()})"


class LabTest(models.Model):
    """Catalog of lab test types."""

    lab = models.ForeignKey(
        Lab,
        on_delete=models.CASCADE,
        related_name="tests",
        null=True,
        blank=True,
        help_text="Null = test available at any lab",
    )
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=32, blank=True)
    reference_range = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["lab"]), models.Index(fields=["code"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class LabIntegrationDevice(models.Model):
    """Configured analyzer / middleware endpoint for a clinic."""

    class ConnectionKind(models.TextChoices):
        HL7_MLLP = "hl7_mllp", "HL7 MLLP"
        HL7_FILE = "hl7_file", "HL7 file"
        FILE_DROP = "file_drop", "File drop / JSON payload"
        SQL_POLL = "sql_poll", "SQL poll"
        REST_WEBHOOK = "rest_webhook", "REST webhook"
        REST_POLL = "rest_poll", "REST poll"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="lab_integration_devices",
    )
    lab = models.ForeignKey(
        Lab,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_devices",
    )
    name = models.CharField(max_length=255)
    vendor = models.CharField(max_length=128, blank=True)
    device_model = models.CharField(
        max_length=128,
        blank=True,
        help_text="Analyzer model name",
    )
    connection_kind = models.CharField(
        max_length=32,
        choices=ConnectionKind.choices,
        default=ConnectionKind.FILE_DROP,
    )
    config = models.JSONField(default=dict, blank=True)
    ingest_token = models.CharField(
        max_length=128,
        blank=True,
        help_text="Shared secret for POST ingest; compare with X-Lab-Ingest-Token header.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["clinic", "is_active"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_connection_kind_display()})"


class LabOrder(models.Model):
    """Order for lab tests - sent to in-clinic or external lab."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        IN_PROGRESS = "in_progress", "In Progress"
        PARTIAL_RESULT = "partial_result", "Partial result"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="lab_orders",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="lab_orders",
    )
    lab = models.ForeignKey(
        Lab,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    clinical_notes = models.TextField(blank=True)
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_orders",
    )
    hospital_stay = models.ForeignKey(
        HospitalStay,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_orders",
    )

    ordered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_orders_created",
    )
    ordered_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    external_accession_number = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
    )
    integration_device = models.ForeignKey(
        LabIntegrationDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_orders",
    )

    class Meta:
        ordering = ["-ordered_at"]
        indexes = [
            models.Index(fields=["clinic", "status"]),
            models.Index(fields=["patient"]),
            models.Index(fields=["clinic", "external_accession_number"]),
        ]

    def __str__(self) -> str:
        return f"LabOrder #{self.id} {self.patient} @ {self.lab} ({self.status})"


class LabOrderLine(models.Model):
    """Single test requested in a lab order."""

    order = models.ForeignKey(
        LabOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    test = models.ForeignKey(
        LabTest,
        on_delete=models.PROTECT,
        related_name="order_lines",
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("order", "test")]
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.order} - {self.test}"


class LabResult(models.Model):
    """Result for a single test in a lab order."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        INTEGRATION = "integration", "Integration"
        MIXED = "mixed", "Mixed"

    order_line = models.OneToOneField(
        LabOrderLine,
        on_delete=models.CASCADE,
        related_name="result",
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    integration_updated_at = models.DateTimeField(null=True, blank=True)
    primary_observation = models.ForeignKey(
        "LabObservation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    value = models.CharField(max_length=255, blank=True)
    value_numeric = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    unit = models.CharField(max_length=32, blank=True)
    reference_range = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_results_entered",
    )

    class Meta:
        ordering = ["order_line__test__name"]

    def __str__(self) -> str:
        return f"LabResult {self.order_line.test} = {self.value or self.value_numeric}"


class LabSample(models.Model):
    """Specimen tied to a lab order (barcode / accession on tube)."""

    class SampleStatus(models.TextChoices):
        PLANNED = "planned", "Planned"
        COLLECTED = "collected", "Collected"
        SENT = "sent", "Sent"
        REJECTED = "rejected", "Rejected"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="lab_samples",
    )
    lab_order = models.ForeignKey(
        LabOrder,
        on_delete=models.CASCADE,
        related_name="samples",
    )
    internal_sample_code = models.CharField(
        max_length=128,
        help_text="Clinic-issued sample ID printed on label",
    )
    sample_type = models.CharField(max_length=64, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=SampleStatus.choices,
        default=SampleStatus.PLANNED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("clinic", "internal_sample_code"),
                name="labs_labsample_clinic_internal_code_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["lab_order"]),
        ]

    def __str__(self) -> str:
        return f"LabSample {self.internal_sample_code} (order {self.lab_order_id})"


class LabExternalIdentifier(models.Model):
    """External IDs (barcode, LIS accession, …) for resolution."""

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="lab_external_identifiers",
    )
    sample = models.ForeignKey(
        LabSample,
        on_delete=models.CASCADE,
        related_name="external_ids",
    )
    scheme = models.CharField(max_length=64)
    value = models.CharField(max_length=256)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("clinic", "scheme", "value"),
                name="labs_labextid_clinic_scheme_value_uniq",
            ),
        ]
        indexes = [models.Index(fields=["clinic", "scheme"])]

    def __str__(self) -> str:
        return f"{self.scheme}:{self.value}"


class LabIngestionEnvelope(models.Model):
    """One inbound payload (idempotent unit of work)."""

    class SourceType(models.TextChoices):
        HL7 = "hl7", "HL7"
        FILE = "file", "File"
        SQL = "sql", "SQL"
        API = "api", "API"
        MANUAL = "manual_upload", "Manual upload"

    class ProcessingStatus(models.TextChoices):
        RECEIVED = "received", "Received"
        PARSING = "parsing", "Parsing"
        PARSED = "parsed", "Parsed"
        MAPPING = "mapping", "Mapping"
        ATTACHING = "attaching", "Attaching"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        ERROR = "error", "Error"
        DEAD_LETTER = "dead_letter", "Dead letter"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="lab_ingestion_envelopes",
    )
    device = models.ForeignKey(
        LabIntegrationDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingestion_envelopes",
    )
    idempotency_key = models.CharField(max_length=512)
    source_type = models.CharField(
        max_length=32,
        choices=SourceType.choices,
        default=SourceType.API,
    )
    processing_status = models.CharField(
        max_length=32,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.RECEIVED,
    )
    raw_file = models.FileField(
        upload_to="lab_ingestion/%Y/%m/%d/",
        blank=True,
        null=True,
        max_length=512,
    )
    raw_body_text = models.TextField(
        blank=True,
        help_text="Small payloads (e.g. tests); prefer raw_file for large data in production.",
    )
    raw_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    raw_s3_bucket = models.CharField(
        max_length=255,
        blank=True,
        help_text="When set with raw_s3_key, raw bytes are loaded from S3 for parsing/reprocess.",
    )
    raw_s3_key = models.CharField(max_length=1024, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    parsed_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    error_detail = models.CharField(max_length=512, blank=True)
    payload_metadata = models.JSONField(default=dict, blank=True)
    correlation_id = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("clinic", "idempotency_key"),
                name="labs_labingestion_clinic_idempotency_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["clinic", "processing_status"]),
        ]

    def __str__(self) -> str:
        return f"IngestionEnvelope {self.id} ({self.processing_status})"


class LabTestCodeMap(models.Model):
    """Maps vendor analyzer codes to catalog LabTest rows."""

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="lab_test_code_maps",
    )
    device = models.ForeignKey(
        LabIntegrationDevice,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="test_code_maps",
    )
    vendor_code = models.CharField(max_length=128)
    vendor_unit = models.CharField(max_length=64, blank=True)
    lab_test = models.ForeignKey(
        LabTest,
        on_delete=models.CASCADE,
        related_name="vendor_code_maps",
    )
    priority = models.IntegerField(default=0)
    species = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-priority", "vendor_code"]
        indexes = [
            models.Index(fields=["clinic", "vendor_code"]),
            models.Index(fields=["device", "vendor_code"]),
        ]

    def __str__(self) -> str:
        return f"{self.vendor_code} → {self.lab_test.code}"


class LabObservation(models.Model):
    """Single parsed measurement from an instrument payload."""

    class MatchStatus(models.TextChoices):
        MATCHED = "matched", "Matched"
        UNMATCHED = "unmatched", "Unmatched"
        AMBIGUOUS = "ambiguous", "Ambiguous"
        SUPPRESSED = "suppressed", "Suppressed"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="lab_observations",
    )
    envelope = models.ForeignKey(
        LabIngestionEnvelope,
        on_delete=models.CASCADE,
        related_name="observations",
    )
    device = models.ForeignKey(
        LabIntegrationDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="observations",
    )
    lab_order = models.ForeignKey(
        LabOrder,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="lab_observations",
    )
    lab_order_line = models.ForeignKey(
        LabOrderLine,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="lab_observations",
    )
    sample = models.ForeignKey(
        LabSample,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_observations",
    )
    match_status = models.CharField(
        max_length=20,
        choices=MatchStatus.choices,
        default=MatchStatus.UNMATCHED,
    )
    vendor_test_code = models.CharField(max_length=128, blank=True)
    vendor_test_name = models.CharField(max_length=255, blank=True)
    internal_test = models.ForeignKey(
        LabTest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_observations",
    )
    value_text = models.CharField(max_length=512, blank=True)
    value_numeric = models.DecimalField(
        max_digits=16,
        decimal_places=6,
        null=True,
        blank=True,
    )
    unit = models.CharField(max_length=64, blank=True)
    ref_low = models.CharField(max_length=64, blank=True)
    ref_high = models.CharField(max_length=64, blank=True)
    abnormal_flag = models.CharField(max_length=32, blank=True)
    result_status = models.CharField(
        max_length=32,
        blank=True,
        help_text="e.g. preliminary / final from HL7",
    )
    natural_key = models.CharField(
        max_length=128,
        help_text="Unique within envelope (row index, OBX id, …)",
    )
    observed_at = models.DateTimeField(null=True, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["envelope_id", "natural_key"]
        constraints = [
            models.UniqueConstraint(
                fields=("envelope", "natural_key"),
                name="labs_labobs_envelope_natural_key_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["clinic", "match_status"]),
            models.Index(fields=["lab_order"]),
        ]

    def __str__(self) -> str:
        return f"Obs {self.vendor_test_code} ({self.match_status})"


class LabResultComponent(models.Model):
    """Clinical result row under a LabResult (panel / multi-analyte)."""

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="lab_result_components",
    )
    lab_result = models.ForeignKey(
        LabResult,
        on_delete=models.CASCADE,
        related_name="components",
    )
    lab_test = models.ForeignKey(
        LabTest,
        on_delete=models.CASCADE,
        related_name="result_components",
    )
    source_observation = models.ForeignKey(
        LabObservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="result_components",
    )
    value_text = models.CharField(max_length=512, blank=True)
    value_numeric = models.DecimalField(
        max_digits=16,
        decimal_places=6,
        null=True,
        blank=True,
    )
    unit = models.CharField(max_length=64, blank=True)
    ref_low = models.CharField(max_length=64, blank=True)
    ref_high = models.CharField(max_length=64, blank=True)
    abnormal_flag = models.CharField(max_length=32, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "lab_test__name"]
        constraints = [
            models.UniqueConstraint(
                fields=("lab_result", "lab_test"),
                name="labs_labrescomp_result_test_uniq",
            ),
        ]
        indexes = [models.Index(fields=["clinic", "lab_result"])]

    def __str__(self) -> str:
        return f"{self.lab_test.code} @ result {self.lab_result_id}"
