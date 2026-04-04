from __future__ import annotations

from datetime import datetime
from datetime import time as dt_time

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.medical.models import ClinicalExam, Vaccination
from apps.patients.models import Patient
from apps.scheduling.models import Appointment

from .authentication import PortalPrincipal
from .permissions import IsPortalClient


class PortalMePatientsView(APIView):
    permission_classes = [IsPortalClient]

    def get(self, request):
        assert isinstance(request.user, PortalPrincipal)
        p = request.user
        patients = Patient.objects.filter(
            clinic_id=p.portal_clinic_id,
            owner_id=p.client_id,
        ).order_by("name", "id")
        data = [
            {
                "id": pt.id,
                "name": pt.name,
                "species": pt.species,
                "breed": pt.breed,
            }
            for pt in patients
        ]
        return Response(data)


class PortalPatientDetailView(APIView):
    """
    GET /api/portal/me/patients/<patient_id>/
    Owner-facing pet card: demographics, upcoming visits, recent vaccinations, last recorded weight.
    """

    permission_classes = [IsPortalClient]

    def get(self, request, patient_id: int):
        assert isinstance(request.user, PortalPrincipal)
        p = request.user

        patient = (
            Patient.objects.filter(
                id=patient_id,
                clinic_id=p.portal_clinic_id,
                owner_id=p.client_id,
            )
            .select_related("primary_vet")
            .first()
        )
        if not patient:
            return Response({"detail": "Patient not found."}, status=404)

        pv = patient.primary_vet
        patient_payload = {
            "id": patient.id,
            "name": patient.name,
            "species": patient.species,
            "breed": patient.breed,
            "sex": patient.sex,
            "birth_date": patient.birth_date.isoformat() if patient.birth_date else None,
            "microchip_no": patient.microchip_no,
            "allergies": patient.allergies,
            "primary_vet_id": patient.primary_vet_id,
            "primary_vet_name": (pv.get_full_name() or pv.username) if pv else "",
        }

        tz = timezone.get_current_timezone()
        start_of_today = timezone.make_aware(
            datetime.combine(timezone.localdate(), dt_time.min),
            tz,
        )
        upcoming = (
            Appointment.objects.filter(
                clinic_id=p.portal_clinic_id,
                patient_id=patient.id,
                starts_at__gte=start_of_today,
            )
            .exclude(status=Appointment.Status.CANCELLED)
            .select_related("vet")
            .order_by("starts_at")[:25]
        )
        upcoming_payload = [
            {
                "id": a.id,
                "starts_at": a.starts_at.isoformat(),
                "ends_at": a.ends_at.isoformat(),
                "status": a.status,
                "reason": a.reason,
                "vet_id": a.vet_id,
                "vet_name": (a.vet.get_full_name() or a.vet.username) if a.vet_id else "",
            }
            for a in upcoming
        ]

        vaccinations = Vaccination.objects.filter(
            clinic_id=p.portal_clinic_id,
            patient_id=patient.id,
        ).order_by("-administered_at", "-id")[:15]
        vaccination_payload = [
            {
                "id": v.id,
                "vaccine_name": v.vaccine_name,
                "batch_number": v.batch_number,
                "administered_at": v.administered_at.isoformat(),
                "next_due_at": v.next_due_at.isoformat() if v.next_due_at else None,
                "notes": v.notes,
            }
            for v in vaccinations
        ]

        last_exam = (
            ClinicalExam.objects.filter(
                clinic_id=p.portal_clinic_id,
                appointment__patient_id=patient.id,
                appointment__status=Appointment.Status.COMPLETED,
                weight_kg__isnull=False,
            )
            .select_related("appointment")
            .order_by("-appointment__starts_at")
            .first()
        )
        last_weight = None
        last_weight_recorded_at = None
        if last_exam and last_exam.weight_kg is not None:
            last_weight = float(last_exam.weight_kg)
            last_weight_recorded_at = last_exam.appointment.starts_at.isoformat()

        return Response(
            {
                "patient": patient_payload,
                "upcoming_appointments": upcoming_payload,
                "recent_vaccinations": vaccination_payload,
                "last_weight_kg": last_weight,
                "last_weight_recorded_at": last_weight_recorded_at,
            },
        )
