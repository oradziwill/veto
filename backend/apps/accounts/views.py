from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .permissions import HasClinic, IsClinicAdmin
from .serializers import (
    ClinicUserReadSerializer,
    ClinicUserWriteSerializer,
    MeSerializer,
    VetSerializer,
)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class VetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    React dropdown use-case:
    - return vets in the current user's clinic
    - if user has no clinic, return empty list (safe MVP)
    """

    serializer_class = VetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            return User.objects.none()

        return User.objects.filter(is_vet=True, clinic_id=user.clinic_id).order_by(
            "last_name", "first_name", "username"
        )


class ClinicUserViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, HasClinic, IsClinicAdmin]

    def get_queryset(self):
        return User.objects.filter(clinic_id=self.request.user.clinic_id).order_by(
            "last_name", "first_name", "username"
        )

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ClinicUserReadSerializer
        return ClinicUserWriteSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["clinic"] = self.request.user.clinic
        return ctx

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.id == self.request.user.id and "role" in serializer.validated_data:
            new_role = serializer.validated_data["role"]
            if new_role != User.Role.ADMIN:
                raise ValidationError(
                    {"role": "You cannot remove admin role from your own account."}
                )
        serializer.save()
