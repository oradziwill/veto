from __future__ import annotations

from django.db.models import Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User

from .view_helpers import dump_public_availability, public_clinic_or_404


class PortalClinicPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        err, clinic = public_clinic_or_404(slug)
        if err:
            return err
        deposit_amt = clinic.effective_portal_deposit_amount()
        return Response(
            {
                "slug": clinic.slug,
                "name": clinic.name,
                "online_booking_enabled": clinic.online_booking_enabled,
                "portal_booking_deposit_pln": str(deposit_amt),
                "portal_booking_deposit_label": clinic.portal_booking_deposit_line_label,
            }
        )


class PortalClinicVetsPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        err, clinic = public_clinic_or_404(slug)
        if err:
            return err
        vets = (
            User.objects.filter(clinic_id=clinic.id)
            .filter(Q(role=User.Role.DOCTOR) | Q(is_vet=True))
            .order_by("last_name", "first_name", "username")
        )
        payload = [
            {
                "id": v.id,
                "first_name": v.first_name or "",
                "last_name": v.last_name or "",
                "username": v.username,
            }
            for v in vets
        ]
        return Response(payload)


class PortalClinicAvailabilityPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        err, clinic = public_clinic_or_404(slug)
        if err:
            return err
        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"detail": "Missing query param: date=YYYY-MM-DD"}, status=400)
        vet_raw = request.query_params.get("vet")
        vet_id = int(vet_raw) if vet_raw else None
        if vet_id is not None:
            if (
                not User.objects.filter(
                    id=vet_id,
                    clinic_id=clinic.id,
                )
                .filter(Q(role=User.Role.DOCTOR) | Q(is_vet=True))
                .exists()
            ):
                return Response({"detail": "Vet not found in this clinic."}, status=404)
        room_raw = request.query_params.get("room")
        room_id = int(room_raw) if room_raw else None
        body = dump_public_availability(clinic.id, date_str, vet_id, room_id)
        return Response(body)
