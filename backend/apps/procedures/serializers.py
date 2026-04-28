from __future__ import annotations

from rest_framework import serializers

from .models import ClinicalProcedure, VisitProcedureSession


class ClinicalProcedureListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalProcedure
        fields = ["id", "slug", "name", "category", "species", "tags", "source"]


class ClinicalProcedureDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalProcedure
        fields = [
            "id",
            "slug",
            "name",
            "name_en",
            "category",
            "species",
            "entry_node_id",
            "nodes",
            "tags",
            "source",
            "last_reviewed",
            "reviewed_by",
        ]


class VisitProcedureSessionSerializer(serializers.ModelSerializer):
    procedure_name = serializers.CharField(source="procedure.name", read_only=True)

    class Meta:
        model = VisitProcedureSession
        fields = [
            "id",
            "appointment",
            "procedure",
            "procedure_name",
            "doctor",
            "patient",
            "path",
            "collected_data",
            "result",
            "result_node_id",
            "completed_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "procedure_name"]
