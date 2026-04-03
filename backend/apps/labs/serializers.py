from rest_framework import serializers

from apps.tenancy.access import (
    clinic_id_for_mutation,
    user_can_access_clinic,
)

from .models import (
    Lab,
    LabExternalIdentifier,
    LabIngestionEnvelope,
    LabIntegrationDevice,
    LabObservation,
    LabOrder,
    LabOrderLine,
    LabResult,
    LabResultComponent,
    LabSample,
    LabTest,
    LabTestCodeMap,
)


class LabSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lab
        fields = [
            "id",
            "name",
            "lab_type",
            "clinic",
            "address",
            "phone",
            "email",
            "is_active",
            "created_at",
        ]


class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = [
            "id",
            "code",
            "name",
            "description",
            "unit",
            "reference_range",
            "lab",
            "is_active",
        ]


class LabResultComponentSerializer(serializers.ModelSerializer):
    test_code = serializers.CharField(source="lab_test.code", read_only=True)
    test_name = serializers.CharField(source="lab_test.name", read_only=True)

    class Meta:
        model = LabResultComponent
        fields = [
            "id",
            "lab_test",
            "test_code",
            "test_name",
            "value_text",
            "value_numeric",
            "unit",
            "ref_low",
            "ref_high",
            "abnormal_flag",
            "sort_order",
            "source_observation",
        ]


class LabResultSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="order_line.test.name", read_only=True)
    test_code = serializers.CharField(source="order_line.test.code", read_only=True)
    components = LabResultComponentSerializer(many=True, read_only=True)

    class Meta:
        model = LabResult
        fields = [
            "id",
            "order_line",
            "test_name",
            "test_code",
            "source",
            "integration_updated_at",
            "primary_observation",
            "value",
            "value_numeric",
            "unit",
            "reference_range",
            "status",
            "notes",
            "completed_at",
            "components",
        ]


class LabOrderLineSerializer(serializers.ModelSerializer):
    test_detail = LabTestSerializer(source="test", read_only=True)
    result = LabResultSerializer(read_only=True)

    class Meta:
        model = LabOrderLine
        fields = ["id", "test", "test_detail", "notes", "result"]


class LabOrderLineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabOrderLine
        fields = ["test", "notes"]


class LabOrderReadSerializer(serializers.ModelSerializer):
    lines = LabOrderLineSerializer(many=True, read_only=True)
    lab_name = serializers.CharField(source="lab.name", read_only=True)

    class Meta:
        model = LabOrder
        fields = [
            "id",
            "clinic",
            "patient",
            "lab",
            "lab_name",
            "status",
            "clinical_notes",
            "appointment",
            "hospital_stay",
            "ordered_by",
            "ordered_at",
            "completed_at",
            "lines",
        ]


class LabOrderWriteSerializer(serializers.ModelSerializer):
    lines = LabOrderLineWriteSerializer(many=True)

    class Meta:
        model = LabOrder
        fields = [
            "patient",
            "lab",
            "clinical_notes",
            "appointment",
            "hospital_stay",
            "lines",
        ]

    def validate_patient(self, value):
        user = self.context["request"].user
        if not user_can_access_clinic(user, value.clinic_id):
            raise serializers.ValidationError("Patient must belong to your clinic.")
        return value

    def validate_lab(self, value):
        user = self.context["request"].user
        if value.clinic_id and not user_can_access_clinic(user, value.clinic_id):
            raise serializers.ValidationError("Lab must belong to your clinic.")
        if not value.clinic_id and value.lab_type != "external":
            raise serializers.ValidationError("External lab must have lab_type=external.")
        return value

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        request = self.context["request"]
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        order = LabOrder.objects.create(
            clinic_id=cid,
            ordered_by=request.user,
            status="draft",
            **validated_data,
        )
        for line_data in lines_data:
            line = LabOrderLine.objects.create(order=order, **line_data)
            LabResult.objects.create(order_line=line)
        return order


class LabResultWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabResult
        fields = [
            "value",
            "value_numeric",
            "unit",
            "reference_range",
            "status",
            "notes",
        ]


class LabIntegrationDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabIntegrationDevice
        fields = [
            "id",
            "clinic",
            "lab",
            "name",
            "vendor",
            "device_model",
            "connection_kind",
            "config",
            "ingest_token",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["clinic", "created_at", "updated_at"]
        extra_kwargs = {"ingest_token": {"write_only": True, "required": False}}

    def create(self, validated_data):
        request = self.context["request"]
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        return LabIntegrationDevice.objects.create(
            clinic_id=cid,
            **validated_data,
        )


class LabExternalIdentifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabExternalIdentifier
        fields = ["id", "clinic", "sample", "scheme", "value"]
        read_only_fields = ["id", "clinic", "sample"]


class _IdentifierPairSerializer(serializers.Serializer):
    scheme = serializers.CharField(max_length=64)
    value = serializers.CharField(max_length=256)


class LabSampleWriteSerializer(serializers.ModelSerializer):
    identifiers = _IdentifierPairSerializer(many=True, required=False)

    class Meta:
        model = LabSample
        fields = [
            "id",
            "lab_order",
            "internal_sample_code",
            "sample_type",
            "collected_at",
            "status",
            "identifiers",
        ]
        read_only_fields = ["id"]

    def validate_lab_order(self, order):
        user = self.context["request"].user
        if not user_can_access_clinic(user, order.clinic_id):
            raise serializers.ValidationError("Order must belong to your clinic.")
        return order

    def create(self, validated_data):
        idents = validated_data.pop("identifiers", [])
        request = self.context["request"]
        order = validated_data.get("lab_order")
        ic = order.clinic_id if order else None
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=ic)
        sample = LabSample.objects.create(
            clinic_id=cid,
            **validated_data,
        )
        for row in idents:
            LabExternalIdentifier.objects.create(
                clinic_id=cid,
                sample=sample,
                scheme=row["scheme"],
                value=row["value"],
            )
        return sample


class LabSampleReadSerializer(serializers.ModelSerializer):
    identifiers = LabExternalIdentifierSerializer(many=True, read_only=True, source="external_ids")

    class Meta:
        model = LabSample
        fields = [
            "id",
            "clinic",
            "lab_order",
            "internal_sample_code",
            "sample_type",
            "collected_at",
            "status",
            "created_at",
            "identifiers",
        ]


class LabTestCodeMapSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTestCodeMap
        fields = [
            "id",
            "clinic",
            "device",
            "vendor_code",
            "vendor_unit",
            "lab_test",
            "priority",
            "species",
        ]


class LabIngestionEnvelopeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabIngestionEnvelope
        fields = [
            "id",
            "clinic",
            "device",
            "idempotency_key",
            "source_type",
            "processing_status",
            "raw_sha256",
            "raw_s3_bucket",
            "raw_s3_key",
            "received_at",
            "parsed_at",
            "error_code",
            "error_detail",
            "payload_metadata",
            "correlation_id",
        ]


class LabObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabObservation
        fields = [
            "id",
            "clinic",
            "envelope",
            "device",
            "lab_order",
            "lab_order_line",
            "sample",
            "match_status",
            "vendor_test_code",
            "vendor_test_name",
            "internal_test",
            "value_text",
            "value_numeric",
            "unit",
            "ref_low",
            "ref_high",
            "abnormal_flag",
            "result_status",
            "natural_key",
            "observed_at",
            "ingested_at",
        ]
