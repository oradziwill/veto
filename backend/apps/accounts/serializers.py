from rest_framework import serializers

from .models import User


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "role",
            "is_vet",
            "clinic",
            "is_staff",
            "is_superuser",
        ]


class VetSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class ClinicUserReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
            "is_vet",
            "clinic",
        ]
        read_only_fields = fields


class ClinicUserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = User
        fields = [
            "username",
            "password",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
        ]

    def validate_username(self, value):
        instance = getattr(self, "instance", None)
        qs = User.objects.filter(username=value)
        if instance is not None:
            qs = qs.exclude(id=instance.id)
        if qs.exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        clinic = self.context["clinic"]
        role = validated_data.get("role", User.Role.RECEPTIONIST)
        user = User(
            clinic=clinic,
            is_staff=True,
            is_vet=(role == User.Role.DOCTOR),
            **validated_data,
        )
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        role = validated_data.get("role", instance.role)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.is_vet = role == User.Role.DOCTOR
        if password:
            instance.set_password(password)
        instance.save()
        return instance
