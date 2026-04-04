from rest_framework import serializers

from .models import WebhookEventType, WebhookSubscription


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookSubscription
        fields = (
            "id",
            "target_url",
            "description",
            "secret",
            "event_types",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {"secret": {"write_only": True}}

    def validate_event_types(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("event_types must be a non-empty list.")
        allowed = {c[0] for c in WebhookEventType.choices}
        bad = [x for x in value if x not in allowed]
        if bad:
            raise serializers.ValidationError(f"Unknown event types: {bad}")
        # de-dupe, stable order
        seen = []
        for x in value:
            if x not in seen:
                seen.append(x)
        return seen

    def validate_target_url(self, value: str) -> str:
        v = (value or "").strip()
        if not v.lower().startswith("https://") and not v.lower().startswith("http://"):
            raise serializers.ValidationError("URL must start with http:// or https://")
        return v
