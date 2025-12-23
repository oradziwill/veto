from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.inventory.views import InventoryItemViewSet, InventoryMovementViewSet

router = DefaultRouter()
router.register(r"inventory/items", InventoryItemViewSet, basename="inventory-items")
router.register(r"inventory/movements", InventoryMovementViewSet, basename="inventory-movements")

urlpatterns = [
    path("", include(router.urls)),
]
