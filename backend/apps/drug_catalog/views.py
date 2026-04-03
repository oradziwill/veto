from __future__ import annotations

from django.db import IntegrityError
from django.db.models import Q, TextField
from django.db.models.functions import Cast
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin, IsStaffOrVet
from apps.tenancy.access import (
    accessible_clinic_ids,
    clinic_id_for_mutation,
)

from .models import ClinicProductMapping, ReferenceProduct
from .serializers import (
    ClinicProductMappingReadSerializer,
    ClinicProductMappingWriteSerializer,
    ReferenceProductCreateSerializer,
    ReferenceProductDetailSerializer,
    ReferenceProductListSerializer,
)


class DrugCatalogPagination(LimitOffsetPagination):
    default_limit = 30
    max_limit = 100


class ReferenceProductSearchView(ListAPIView):
    """
    GET /api/drug-catalog/search/?q=&species=
    """

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = ReferenceProductListSerializer
    pagination_class = DrugCatalogPagination

    def get_queryset(self):
        qs = ReferenceProduct.objects.all().order_by("name")
        q = (self.request.query_params.get("q") or "").strip()
        species = (self.request.query_params.get("species") or "").strip()

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(common_name__icontains=q))
        if species:
            qs = qs.annotate(_payload_text=Cast("payload", TextField())).filter(
                _payload_text__icontains=species
            )
        return qs


class ReferenceProductViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST /api/drug-catalog/products/ — create manual reference row (doctor or clinic admin only).
    GET /api/drug-catalog/products/<id>/ — detail (staff/vet).
    """

    queryset = ReferenceProduct.objects.all()

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), HasClinic(), IsDoctorOrAdmin()]
        return [IsAuthenticated(), HasClinic(), IsStaffOrVet()]

    def get_serializer_class(self):
        if self.action == "create":
            return ReferenceProductCreateSerializer
        return ReferenceProductDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        out = ReferenceProductDetailSerializer(serializer.instance)
        return Response(out.data, status=201)


class ClinicProductMappingViewSet(viewsets.ModelViewSet):
    """
    GET/POST/PATCH /api/drug-catalog/mappings/
    """

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return (
            ClinicProductMapping.objects.filter(
                clinic_id__in=accessible_clinic_ids(self.request.user)
            )
            .select_related("reference_product", "inventory_item", "clinic")
            .order_by("-updated_at")
        )

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ClinicProductMappingReadSerializer
        return ClinicProductMappingWriteSerializer

    def perform_create(self, serializer):
        try:
            cid = clinic_id_for_mutation(
                self.request.user, request=self.request, instance_clinic_id=None
            )
            serializer.save(clinic_id=cid)
        except IntegrityError as exc:
            raise ValidationError(
                {
                    "non_field_errors": [
                        "A mapping already exists for this clinic and inventory line "
                        "or for this clinic and reference product without inventory."
                    ]
                }
            ) from exc
