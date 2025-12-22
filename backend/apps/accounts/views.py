from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializers import MeSerializer, VetSerializer


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

        return (
            User.objects.filter(is_vet=True, clinic_id=user.clinic_id)
            .order_by("last_name", "first_name", "username")
        )
