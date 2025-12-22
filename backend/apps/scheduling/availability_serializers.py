from rest_framework import serializers


class IntervalSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()


class BusyIntervalSerializer(serializers.Serializer):
    appointment_id = serializers.IntegerField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()


class AvailabilityResponseSerializer(serializers.Serializer):
    date = serializers.CharField()
    timezone = serializers.CharField()
    clinic_id = serializers.IntegerField()
    vet_id = serializers.IntegerField(allow_null=True)
    slot_minutes = serializers.IntegerField()

    # Backward-compatible "bounds"
    workday = IntervalSerializer()

    # New: multiple intervals per day
    work_intervals = IntervalSerializer(many=True)

    busy = BusyIntervalSerializer(many=True)
    free = IntervalSerializer(many=True)
