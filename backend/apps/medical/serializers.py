from __future__ import annotations

from rest_framework import serializers

from apps.medical.models import (
    ClinicalExam,
    MedicalRecord,
    PatientHistoryEntry,
    Prescription,
    Vaccination,
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
            "additional_notes",
            "owner_instructions",
            "initial_diagnosis",
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
        if request and value.clinic_id != getattr(request.user, "clinic_id", None):
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
    class Meta:
        model = PatientHistoryEntry
        fields = [
            "id",
            "clinic",
            "record",
            "note",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class PatientHistoryEntryWriteSerializer(serializers.ModelSerializer):
    def validate_record(self, value):
        request = self.context.get("request")
        if request and value.clinic_id != getattr(request.user, "clinic_id", None):
            raise serializers.ValidationError("Medical record must belong to your clinic.")
        return value

    class Meta:
        model = PatientHistoryEntry
        fields = [
            "record",
            "note",
        ]


# -------------------------
# Prescription
# -------------------------


class PrescriptionReadSerializer(serializers.ModelSerializer):
    prescribed_by_name = serializers.SerializerMethodField()

    def get_prescribed_by_name(self, obj):
        if not obj.prescribed_by:
            return None
        return obj.prescribed_by.get_full_name() or obj.prescribed_by.username

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
            "created_at",
        ]
        read_only_fields = fields


class PrescriptionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = [
            "medical_record",
            "drug_name",
            "dosage",
            "duration_days",
            "notes",
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
        if request and value.clinic_id != getattr(request.user, "clinic_id", None):
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
