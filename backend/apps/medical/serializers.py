from __future__ import annotations

from rest_framework import serializers

from apps.medical.models import ClinicalExam, MedicalRecord, PatientHistoryEntry, Prescription


class MedicalRecordWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        # Keep fields minimal; clinic/patient/created_by are assigned in views.
        fields = ["ai_summary"]


class MedicalRecordReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        fields = ["id", "clinic", "patient", "ai_summary", "created_by", "created_at"]
        read_only_fields = fields


class PatientHistoryEntryReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientHistoryEntry
        fields = ["id", "clinic", "record", "note", "created_by", "created_at"]
        read_only_fields = fields


class PatientHistoryEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientHistoryEntry
        fields = ["note"]


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


class PrescriptionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = [
            "id",
            "clinic",
            "appointment",
            "patient",
            "medication",
            "instructions",
            "quantity",
            "refills",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class PrescriptionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = ["medication", "instructions", "quantity", "refills"]
