from rest_framework import serializers

from .models import ReportExportJob


class ReportExportJobReadSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)

    class Meta:
        model = ReportExportJob
        fields = [
            "id",
            "clinic",
            "requested_by",
            "requested_by_username",
            "report_type",
            "params",
            "status",
            "file_name",
            "content_type",
            "error",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ReportExportJobCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportExportJob
        fields = ["report_type", "params"]

    def validate_params(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("params must be a JSON object.")
        return value
