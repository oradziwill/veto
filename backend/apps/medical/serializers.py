from __future__ import annotations

from rest_framework import serializers

from apps.medical.models import ClinicalExam, MedicalRecord, PatientHistoryEntry

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
