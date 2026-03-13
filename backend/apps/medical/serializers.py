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
    class Meta:
        model = Prescription
        fields = [
            "id",
            "clinic",
            "patient",
            "appointment",
            "medical_record",
            "prescribed_by",
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


# -------------------------
# Vaccination
# -------------------------


class VaccinationReadSerializer(serializers.ModelSerializer):
    administered_by_name = serializers.SerializerMethodField()

    def get_administered_by_name(self, obj):
        if not obj.administered_by:
            return None
        return obj.administered_by.get_full_name() or obj.administered_by.username

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
            "administered_by",
            "administered_by_name",
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
