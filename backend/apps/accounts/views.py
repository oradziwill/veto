from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from .serializers import MeSerializer
from .models import User


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class VetsViewSet(ReadOnlyModelViewSet):
    """
    Returns vets in the current user's clinic.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MeSerializer

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            return User.objects.none()
        
        return User.objects.filter(
            clinic_id=user.clinic_id,
            is_vet=True
        ).order_by("first_name", "last_name")
