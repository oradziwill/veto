from rest_framework import permissions, viewsets

from .models import InventoryItem
from .serializers import InventoryItemSerializer


class InventoryItemViewSet(viewsets.ModelViewSet):
    serializer_class = InventoryItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            return InventoryItem.objects.none()

        qs = InventoryItem.objects.filter(clinic_id=user.clinic_id)

        # Filter by category
        category = self.request.query_params.get("category", "")
        if category:
            qs = qs.filter(category=category)

        # Search by name
        search = self.request.query_params.get("search", "")
        if search:
            qs = qs.filter(name__icontains=search)

        return qs.order_by("name")

    def perform_create(self, serializer):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            raise ValueError("User must belong to a clinic to create inventory items.")
        serializer.save(clinic=user.clinic)
