from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.billing.models import Invoice
from apps.drug_catalog.models import ReferenceProduct
from apps.medical.models import (
    ClinicalExam,
    ClinicalExamTemplate,
    MedicalRecord,
    PatientHistoryEntry,
    Prescription,
    ProcedureSupplyTemplate,
    ProcedureSupplyTemplateLine,
    Vaccination,
)
from apps.scheduling.models import Appointment
from apps.tenancy.access import (
    accessible_clinic_ids,
    clinic_id_for_mutation,
    user_can_access_clinic,
)

# -------------------------
# Clinical Exam
# -------------------------


class ClinicalExamReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalExam
        fields = [
            "id",
            "clinic",
            "appointment",
            "initial_notes",
            "clinical_examination",
            "temperature_c",
            "heart_rate_bpm",
            "respiratory_rate_rpm",
            "weight_kg",
            "additional_notes",
            "owner_instructions",
            "initial_diagnosis",
            "transcript",
            "ai_notes_raw",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ClinicalExamWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalExam
        # clinic/appointment/created_by are set in the view; clients should not send them
        fields = [
            "initial_notes",
            "clinical_examination",
            "temperature_c",
            "heart_rate_bpm",
            "respiratory_rate_rpm",
            "weight_kg",
            "additional_notes",
            "owner_instructions",
            "initial_diagnosis",
        ]

    def validate_temperature_c(self, value):
        # Optional: allow empty
        if value is None:
            return value
        # Basic sanity bounds; adjust/remove if you dislike constraints
        if value < 20 or value > 50:
            raise serializers.ValidationError("temperature_c looks out of range.")
        return value


class ClinicalExamTemplateReadSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name() or obj.created_by.username

    class Meta:
        model = ClinicalExamTemplate
        fields = [
            "id",
            "clinic",
            "name",
            "visit_type",
            "defaults",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ClinicalExamTemplateWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalExamTemplate
        fields = [
            "name",
            "visit_type",
            "defaults",
            "is_active",
        ]

    def validate_defaults(self, value):
        allowed_fields = {
            "initial_notes",
            "clinical_examination",
            "temperature_c",
            "heart_rate_bpm",
            "respiratory_rate_rpm",
            "weight_kg",
            "additional_notes",
            "owner_instructions",
            "initial_diagnosis",
        }
        if not isinstance(value, dict):
            raise serializers.ValidationError("defaults must be a JSON object.")
        invalid = sorted(set(value.keys()) - allowed_fields)
        if invalid:
            raise serializers.ValidationError(f"Unsupported default field(s): {', '.join(invalid)}")
        return value


# -------------------------
# Procedure supply templates (consumables / procedure kits)
# -------------------------


class ProcedureSupplyTemplateLineReadSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    inventory_item_sku = serializers.CharField(source="inventory_item.sku", read_only=True)

    class Meta:
        model = ProcedureSupplyTemplateLine
        fields = [
            "id",
            "inventory_item",
            "inventory_item_name",
            "inventory_item_sku",
            "suggested_quantity",
            "sort_order",
            "is_optional",
            "default_unit_price",
            "vat_rate",
            "notes",
        ]
        read_only_fields = fields


class ProcedureSupplyTemplateLineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcedureSupplyTemplateLine
        fields = [
            "inventory_item",
            "suggested_quantity",
            "sort_order",
            "is_optional",
            "default_unit_price",
            "vat_rate",
            "notes",
        ]

    def validate_inventory_item(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and value.clinic_id not in accessible_clinic_ids(user):
            raise serializers.ValidationError("Inventory item must belong to your clinic.")
        return value

    def validate_suggested_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("suggested_quantity must be positive.")
        if Decimal(str(value)) != Decimal(str(value)).to_integral_value():
            raise serializers.ValidationError(
                "suggested_quantity must be a whole number for inventory items."
            )
        return value


class ProcedureSupplyTemplateReadSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    lines = ProcedureSupplyTemplateLineReadSerializer(many=True, read_only=True)

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name() or obj.created_by.username

    class Meta:
        model = ProcedureSupplyTemplate
        fields = [
            "id",
            "clinic",
            "name",
            "visit_type",
            "is_active",
            "created_by",
            "created_by_name",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ProcedureSupplyTemplateWriteSerializer(serializers.ModelSerializer):
    lines = ProcedureSupplyTemplateLineWriteSerializer(many=True, required=False)

    class Meta:
        model = ProcedureSupplyTemplate
        fields = [
            "name",
            "visit_type",
            "is_active",
            "lines",
        ]

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("This field may not be blank.")
        request = self.context.get("request")
        user = getattr(request, "user", None)
        ids = accessible_clinic_ids(user) if user else []
        if not ids:
            return name
        qs = ProcedureSupplyTemplate.objects.filter(clinic_id__in=ids, name=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A template with this name already exists in your clinic."
            )
        return name

    def validate(self, attrs):
        if self.instance is None:
            lines = attrs.get("lines")
            if not lines:
                raise serializers.ValidationError({"lines": "At least one line is required."})
        return attrs

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        request = self.context["request"]
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        template = ProcedureSupplyTemplate.objects.create(
            clinic_id=cid,
            created_by=request.user,
            **validated_data,
        )
        for line_data in lines_data:
            ProcedureSupplyTemplateLine.objects.create(template=template, **line_data)
        return template

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if lines_data is not None:
            if not lines_data:
                raise serializers.ValidationError({"lines": ["At least one line is required."]})
            instance.lines.all().delete()
            for line_data in lines_data:
                ProcedureSupplyTemplateLine.objects.create(template=instance, **line_data)
        return instance


# -------------------------
# Medical Record (if used elsewhere)
# -------------------------


class MedicalRecordReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        fields = [
            "id",
            "clinic",
            "patient",
            "ai_summary",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class MedicalRecordWriteSerializer(serializers.ModelSerializer):
    def validate_patient(self, value):
        request = self.context.get("request")
        if request and not user_can_access_clinic(request.user, value.clinic_id):
            raise serializers.ValidationError("Patient must belong to your clinic.")
        return value

    class Meta:
        model = MedicalRecord
        fields = [
            "patient",
            "ai_summary",
        ]


# -------------------------
# Patient History Entry (if used elsewhere)
# -------------------------


class PatientHistoryEntryReadSerializer(serializers.ModelSerializer):
    services_performed = serializers.SerializerMethodField()

    def get_services_performed(self, obj):
        invoice = getattr(obj, "invoice", None)
        if not invoice:
            return []
        lines = getattr(invoice, "lines", None)
        if lines is None:
            return []
        return [
            {
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
            }
            for line in lines.all()
        ]

    class Meta:
        model = PatientHistoryEntry
        fields = [
            "id",
            "clinic",
            "record",
            "appointment",
            "invoice",
            "note",
            "services_performed",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class PatientHistoryEntryWriteSerializer(serializers.ModelSerializer):
    invoice = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(),
        required=False,
        allow_null=True,
    )
    appointment = serializers.PrimaryKeyRelatedField(
        queryset=Appointment.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate_record(self, value):
        request = self.context.get("request")
        if request and not user_can_access_clinic(request.user, value.clinic_id):
            raise serializers.ValidationError("Medical record must belong to your clinic.")
        return value

    def validate_invoice(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request and not user_can_access_clinic(request.user, value.clinic_id):
            raise serializers.ValidationError("Invoice must belong to your clinic.")
        patient = self.context.get("patient")
        if patient and value.patient_id and value.patient_id != patient.id:
            raise serializers.ValidationError("Invoice must belong to this patient.")
        return value

    def validate_appointment(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request and not user_can_access_clinic(request.user, value.clinic_id):
            raise serializers.ValidationError("Appointment must belong to your clinic.")
        patient = self.context.get("patient")
        if patient and value.patient_id and value.patient_id != patient.id:
            raise serializers.ValidationError("Appointment must belong to this patient.")
        return value

    class Meta:
        model = PatientHistoryEntry
        fields = [
            "record",
            "appointment",
            "invoice",
            "note",
        ]


# -------------------------
# Prescription
# -------------------------


class PrescriptionReadSerializer(serializers.ModelSerializer):
    prescribed_by_name = serializers.SerializerMethodField()
    reference_product = serializers.SerializerMethodField()

    def get_prescribed_by_name(self, obj):
        if not obj.prescribed_by:
            return None
        return obj.prescribed_by.get_full_name() or obj.prescribed_by.username

    def get_reference_product(self, obj):
        ref = getattr(obj, "reference_product", None)
        if ref is None:
            return None
        return {"id": ref.id, "name": ref.name}

    class Meta:
        model = Prescription
        fields = [
            "id",
            "clinic",
            "patient",
            "appointment",
            "medical_record",
            "prescribed_by",
            "prescribed_by_name",
            "drug_name",
            "dosage",
            "duration_days",
            "notes",
            "reference_product",
            "created_at",
        ]
        read_only_fields = fields


class PrescriptionWriteSerializer(serializers.ModelSerializer):
    reference_product = serializers.PrimaryKeyRelatedField(
        queryset=ReferenceProduct.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Prescription
        fields = [
            "medical_record",
            "drug_name",
            "dosage",
            "duration_days",
            "notes",
            "reference_product",
        ]

    def validate_drug_name(self, value):
        if not (value or "").strip():
            raise serializers.ValidationError("drug_name is required for new prescriptions.")
        return value

    def validate_dosage(self, value):
        if not (value or "").strip():
            raise serializers.ValidationError("dosage is required for new prescriptions.")
        return value

    def validate_medical_record(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request and not user_can_access_clinic(request.user, value.clinic_id):
            raise serializers.ValidationError("Medical record must belong to your clinic.")
        patient = self.context.get("patient")
        if patient and value.patient_id != patient.id:
            raise serializers.ValidationError("Medical record must belong to this patient.")
        return value


# -------------------------
# Vaccination
# -------------------------


class VaccinationReadSerializer(serializers.ModelSerializer):
    administered_by_name = serializers.SerializerMethodField()
    patient_name = serializers.CharField(source="patient.name", read_only=True)
    owner_name = serializers.SerializerMethodField()
    next_due_date = serializers.DateField(source="next_due_at", read_only=True)

    def get_administered_by_name(self, obj):
        if not obj.administered_by:
            return None
        return obj.administered_by.get_full_name() or obj.administered_by.username

    def get_owner_name(self, obj):
        owner = getattr(obj.patient, "owner", None)
        if not owner:
            return None
        full_name = f"{owner.first_name or ''} {owner.last_name or ''}".strip()
        return full_name or None

    class Meta:
        model = Vaccination
        fields = [
            "id",
            "clinic",
            "patient",
            "vaccine_name",
            "batch_number",
            "administered_at",
            "next_due_at",
            "next_due_date",
            "administered_by",
            "administered_by_name",
            "patient_name",
            "owner_name",
            "notes",
        ]
        read_only_fields = fields


class VaccinationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vaccination
        fields = [
            "vaccine_name",
            "batch_number",
            "administered_at",
            "next_due_at",
            "notes",
        ]
