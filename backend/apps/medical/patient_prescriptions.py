from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.medical.models import Prescription
from apps.medical.serializers import PrescriptionReadSerializer
from apps.patients.models import Patient
from apps.tenancy.access import (
    accessible_clinic_ids,
)


class PatientPrescriptionHistoryView(APIView):
    """
    GET /api/patients/<patient_id>/prescriptions/

    Returns the prescription history for a patient scoped to the authenticated user's clinic.
    - 404 if patient not in user's clinic
    - Requires auth + clinic + staff/vet
    """

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get(self, request, patient_id: int):
        user = request.user

        # Clinic scoping: do not reveal existence of patients across clinics.
        patient = Patient.objects.filter(
            id=patient_id, clinic_id__in=accessible_clinic_ids(user)
        ).first()
        if not patient:
            return Response({"detail": "Not found."}, status=404)

        qs = (
            Prescription.objects.filter(
                clinic_id__in=accessible_clinic_ids(user),
                patient_id=patient.id,
            )
            .select_related("appointment", "patient")
            .order_by("-created_at")
        )

        return Response(PrescriptionReadSerializer(qs, many=True).data, status=200)
