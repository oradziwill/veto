from rest_framework.routers import DefaultRouter
from .views import InventoryItemViewSet

router = DefaultRouter()
router.register(r"inventory", InventoryItemViewSet, basename="inventory")

urlpatterns = router.urls

