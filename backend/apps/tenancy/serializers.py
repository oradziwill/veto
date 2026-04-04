from rest_framework import serializers

from .models import Clinic


class ClinicFeatureFlagsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = (
            "feature_ai_enabled",
            "feature_ksef_enabled",
            "feature_portal_deposit_enabled",
        )
