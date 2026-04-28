from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ClinicalProcedureViewSet, VisitProcedureSessionViewSet

router = DefaultRouter()
router.register(r"procedures", ClinicalProcedureViewSet, basename="procedures")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "appointments/<uuid:appointment_pk>/procedure-sessions/",
        VisitProcedureSessionViewSet.as_view({"get": "list", "post": "create"}),
        name="appointment-procedure-sessions",
    ),
    path(
        "appointments/<uuid:appointment_pk>/procedure-sessions/<uuid:pk>/",
        VisitProcedureSessionViewSet.as_view({"patch": "partial_update", "put": "update"}),
        name="appointment-procedure-session-detail",
    ),
]
