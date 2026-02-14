from rest_framework import serializers

from .models import Lab, LabOrder, LabOrderLine, LabResult, LabTest


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


class LabResultSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="order_line.test.name", read_only=True)
    test_code = serializers.CharField(source="order_line.test.code", read_only=True)

    class Meta:
        model = LabResult
        fields = [
            "id",
            "order_line",
            "test_name",
            "test_code",
            "value",
            "value_numeric",
            "unit",
            "reference_range",
            "status",
            "notes",
            "completed_at",
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
        if value.clinic_id != getattr(user, "clinic_id", None):
            raise serializers.ValidationError("Patient must belong to your clinic.")
        return value

    def validate_lab(self, value):
        user = self.context["request"].user
        if value.clinic_id and value.clinic_id != getattr(user, "clinic_id", None):
            raise serializers.ValidationError("Lab must belong to your clinic.")
        if not value.clinic_id and value.lab_type != "external":
            raise serializers.ValidationError("External lab must have lab_type=external.")
        return value

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        request = self.context["request"]
        order = LabOrder.objects.create(
            clinic_id=request.user.clinic_id,
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
