from django.db import models
from rest_framework import viewsets, permissions
from .models import Client
from .serializers import ClientSerializer


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    # Temporarily allow unauthenticated access for development
    # Change back to [permissions.IsAuthenticated] for production
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        from apps.clients.models import ClientClinic
        
        # Search by name, phone, or email (use 'q' parameter as per API docs)
        search = self.request.query_params.get("q", "")
        qs = Client.objects.all()
        
        if search:
            qs = qs.filter(
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(phone__icontains=search) |
                models.Q(email__icontains=search)
            )
        
        # Filter by clinic membership if requested
        in_my_clinic = self.request.query_params.get("in_my_clinic", "")
        if in_my_clinic and hasattr(self.request.user, "clinic_id") and self.request.user.clinic_id:
            clinic_id = self.request.user.clinic_id
            client_ids = ClientClinic.objects.filter(
                clinic_id=clinic_id,
                is_active=True
            ).values_list("client_id", flat=True)
            qs = qs.filter(id__in=client_ids)
        
        return qs.order_by("last_name", "first_name")
