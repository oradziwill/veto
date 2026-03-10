from rest_framework import serializers

from apps.scheduling.models_clinic_hours import ClinicWorkingHours
from apps.scheduling.models_duty import DutyAssignment
from apps.scheduling.models_exceptions import VetAvailabilityException
from apps.scheduling.models_working_hours import VetWorkingHours
from apps.tenancy.models import ClinicHoliday


class VetWorkingHoursSerializer(serializers.ModelSerializer):
    vet_name = serializers.SerializerMethodField()
    weekday_display = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = VetWorkingHours
        fields = [
            "id",
            "vet",
            "vet_name",
            "weekday",
            "weekday_display",
            "start_time",
            "end_time",
            "is_active",
        ]

    def get_vet_name(self, obj):
        return obj.vet.get_full_name() or obj.vet.username

    def validate(self, attrs):
        if attrs.get("end_time") and attrs.get("start_time"):
            if attrs["end_time"] <= attrs["start_time"]:
                raise serializers.ValidationError({"end_time": "end_time must be after start_time"})
        return attrs


class VetAvailabilityExceptionSerializer(serializers.ModelSerializer):
    vet_name = serializers.SerializerMethodField()

    class Meta:
        model = VetAvailabilityException
        fields = [
            "id",
            "vet",
            "vet_name",
            "date",
            "is_day_off",
            "start_time",
            "end_time",
            "note",
        ]
        read_only_fields = ["id"]

    def get_vet_name(self, obj):
        return obj.vet.get_full_name() or obj.vet.username

    def validate(self, attrs):
        is_day_off = attrs.get("is_day_off", False)
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        if not is_day_off:
            if (start_time is None) ^ (end_time is None):
                raise serializers.ValidationError(
                    "Provide both start_time and end_time or neither."
                )
            if start_time and end_time and end_time <= start_time:
                raise serializers.ValidationError(
                    {"end_time": "end_time must be after start_time."}
                )
        return attrs


class ClinicHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicHoliday
        fields = ["id", "date", "reason", "is_active"]
        read_only_fields = ["id"]


class ClinicWorkingHoursSerializer(serializers.ModelSerializer):
    weekday_display = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = ClinicWorkingHours
        fields = [
            "id",
            "weekday",
            "weekday_display",
            "start_time",
            "end_time",
            "is_active",
            "shift_hours",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs.get("end_time") and attrs.get("start_time"):
            if attrs["end_time"] <= attrs["start_time"]:
                raise serializers.ValidationError({"end_time": "end_time must be after start_time"})
        return attrs


class DutyAssignmentSerializer(serializers.ModelSerializer):
    vet_name = serializers.SerializerMethodField()

    class Meta:
        model = DutyAssignment
        fields = [
            "id",
            "vet",
            "vet_name",
            "date",
            "start_time",
            "end_time",
            "is_auto_generated",
            "note",
        ]
        read_only_fields = ["id", "is_auto_generated"]

    def get_vet_name(self, obj):
        return obj.vet.get_full_name() or obj.vet.username
