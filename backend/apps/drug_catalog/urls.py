from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClinicProductMappingViewSet,
    ReferenceProductSearchView,
    ReferenceProductViewSet,
)

router = DefaultRouter()
router.register(r"drug-catalog/products", ReferenceProductViewSet, basename="drug-catalog-products")
router.register(
    r"drug-catalog/mappings", ClinicProductMappingViewSet, basename="drug-catalog-mappings"
)

urlpatterns = [
    path("drug-catalog/search/", ReferenceProductSearchView.as_view(), name="drug-catalog-search"),
    path("", include(router.urls)),
]
