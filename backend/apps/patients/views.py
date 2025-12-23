import os

from apps.accounts.permissions import HasClinic, IsVet
from apps.clients.models import ClientClinic
from apps.medical.models import MedicalRecord, PatientHistoryEntry
from apps.medical.serializers import (
    PatientHistoryEntryReadSerializer,
    PatientHistoryEntryWriteSerializer,
)
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import PatientReadSerializer, PatientWriteSerializer


class PatientViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return PatientReadSerializer
        return PatientWriteSerializer

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            return Patient.objects.none()

        qs = Patient.objects.filter(clinic_id=user.clinic_id).select_related(
            "owner",
            "primary_vet",
            "clinic",
        )

        species = self.request.query_params.get("species")
        owner_id = self.request.query_params.get("owner")
        vet_id = self.request.query_params.get("vet")

        if species:
            qs = qs.filter(species__iexact=species)
        if owner_id:
            qs = qs.filter(owner_id=owner_id)
        if vet_id:
            qs = qs.filter(primary_vet_id=vet_id)

        return qs.order_by("name")

    def perform_create(self, serializer):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            raise ValidationError("User must belong to a clinic to create patients.")

        patient = serializer.save(clinic=user.clinic)

        # Ensure client membership exists (multi-clinic client model)
        if patient.owner_id and patient.clinic_id:
            ClientClinic.objects.get_or_create(
                client_id=patient.owner_id,
                clinic_id=patient.clinic_id,
                defaults={"is_active": True},
            )

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if (
            instance.clinic_id
            and getattr(user, "clinic_id", None) != instance.clinic_id
            and not user.is_superuser
        ):
            raise ValidationError("You cannot modify patients outside your clinic.")

        patient = serializer.save()

        if patient.owner_id and patient.clinic_id:
            ClientClinic.objects.get_or_create(
                client_id=patient.owner_id,
                clinic_id=patient.clinic_id,
                defaults={"is_active": True},
            )

    @action(detail=True, methods=["get", "post"], url_path="history")
    def history(self, request, pk=None):
        """
        GET  /api/patients/<id>/history/  -> list history entries for this patient (clinic scoped)
        POST /api/patients/<id>/history/  -> create new entry (vets only)
        """
        user = request.user
        patient = self.get_object()  # already clinic-filtered by get_queryset

        if request.method == "GET":
            qs = (
                PatientHistoryEntry.objects.filter(
                    clinic_id=user.clinic_id,
                    patient_id=patient.id,
                )
                .select_related("appointment", "created_by")
                .order_by("-created_at")
            )
            return Response(PatientHistoryEntryReadSerializer(qs, many=True).data)

        # POST requires vet
        if not IsVet().has_permission(request, self):
            raise PermissionDenied("Only vets can add history notes.")

        serializer = PatientHistoryEntryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appointment = serializer.validated_data.get("appointment")

        if appointment is not None:
            # Enforce tenant + patient match
            # (This prevents your earlier: "appointment from another clinic")
            if appointment.clinic_id != user.clinic_id:
                raise PermissionDenied("You cannot attach an appointment from another clinic.")
            if appointment.patient_id != patient.id:
                raise PermissionDenied("You cannot attach an appointment for a different patient.")

        entry = PatientHistoryEntry.objects.create(
            clinic_id=user.clinic_id,
            patient_id=patient.id,
            appointment=appointment,
            note=serializer.validated_data["note"],
            receipt_summary=serializer.validated_data.get("receipt_summary", ""),
            created_by=user,
        )

        # Invalidate AI summary cache when a new history entry is added
        patient.ai_summary = ""
        patient.ai_summary_updated_at = None
        patient.save(update_fields=["ai_summary", "ai_summary_updated_at"])

        return Response(PatientHistoryEntryReadSerializer(entry).data, status=201)

    @action(detail=True, methods=["get"], url_path="ai-summary")
    def ai_summary(self, request, pk=None):
        """
        GET /api/patients/<id>/ai-summary/ -> Generate AI summary of patient history and condition
        """
        try:
            from openai import OpenAI
        except ImportError:
            return Response(
                {"error": "OpenAI package not installed. Please install: pip install openai"},
                status=503,
            )

        api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            return Response(
                {
                    "error": "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
                },
                status=503,
            )

        user = request.user
        patient = self.get_object()  # already clinic-filtered by get_queryset

        # Check if we have a cached summary that's still valid
        # Cache is invalid if there are new history entries since the summary was created
        if patient.ai_summary and patient.ai_summary_updated_at:
            # Check if there are any history entries created after the summary was updated
            has_new_history = PatientHistoryEntry.objects.filter(
                clinic_id=user.clinic_id,
                patient_id=patient.id,
                created_at__gt=patient.ai_summary_updated_at,
            ).exists()

            if not has_new_history:
                # Cache is still valid, return it
                return Response(
                    {
                        "summary": patient.ai_summary,
                        "model": "gpt-4o-mini",
                        "cached": True,
                    }
                )

        # Need to generate a new summary
        # Collect visit history (focus on medical history, not basic patient info)
        history_entries = (
            PatientHistoryEntry.objects.filter(
                clinic_id=user.clinic_id,
                patient_id=patient.id,
            )
            .select_related("appointment", "created_by")
            .order_by("-created_at")
        )

        history_data = []
        for entry in history_entries:
            history_item = {
                "date": str(entry.created_at.date()),
                "note": entry.note,
                "receipt_summary": entry.receipt_summary or "",
            }
            if entry.appointment:
                history_item["appointment_reason"] = entry.appointment.reason or ""
            history_data.append(history_item)

        # Collect appointments
        appointments = Appointment.objects.filter(
            clinic_id=user.clinic_id,
            patient_id=patient.id,
        ).order_by("-starts_at")

        appointments_data = []
        for apt in appointments[:10]:  # Limit to last 10
            appointments_data.append(
                {
                    "date": str(apt.starts_at.date()),
                    "reason": apt.reason or "",
                    "status": apt.status,
                    "internal_notes": apt.internal_notes or "",
                }
            )

        # Collect medical records (SOAP notes)
        medical_records = (
            MedicalRecord.objects.filter(
                appointment__patient_id=patient.id, appointment__clinic_id=user.clinic_id
            )
            .select_related("appointment", "created_by")
            .order_by("-created_at")
        )

        medical_records_data = []
        for record in medical_records[:10]:  # Limit to last 10
            medical_records_data.append(
                {
                    "date": str(record.created_at.date()),
                    "subjective": record.subjective or "",
                    "objective": record.objective or "",
                    "assessment": record.assessment or "",
                    "plan": record.plan or "",
                    "weight_kg": float(record.weight_kg) if record.weight_kg else None,
                    "temperature_c": float(record.temperature_c) if record.temperature_c else None,
                }
            )

        # Build focused prompt for executive summary
        prompt = "Create a brief executive summary for a veterinarian. Include:\n"
        prompt += "1. Key medical history and notable events\n"
        prompt += "2. Current medications and prescriptions\n"
        prompt += "3. Important context to remember this patient\n\n"

        # Add allergies if present (critical information)
        if patient.allergies:
            prompt += f"ALLERGIES: {patient.allergies}\n\n"

        # Extract medications from visit history, receipts, and medical records
        # Collect visit history
        if history_data:
            prompt += f"Visit Notes (last {min(len(history_data), 10)} visits):\n"
            for entry in history_data[:10]:  # Limit to last 10
                prompt += f"- {entry['date']}: {entry['note']}\n"
                if entry["receipt_summary"]:
                    prompt += f"  Medications/Treatment: {entry['receipt_summary']}\n"

        # Add medical records (focus on plan/medications)
        if medical_records_data:
            prompt += "\nMedical Records:\n"
            for record in medical_records_data[:5]:  # Limit to last 5
                if record["assessment"] or record["plan"]:
                    prompt += f"- {record['date']}: "
                    if record["assessment"]:
                        prompt += f"Assessment: {record['assessment']} "
                    if record["plan"]:
                        prompt += f"Plan: {record['plan']}"
                    prompt += "\n"

        prompt += "\nProvide a concise executive summary (1-2 short paragraphs) covering: medical history highlights, current medications/prescriptions, and key patient context."

        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a veterinary assistant creating executive summaries. Write brief, focused summaries (1-2 paragraphs max) that help doctors quickly remember the patient's history, understand current medications/prescriptions, and recall important context. Do NOT include patient name, species, or breed. Be concise and focus only on essential medical information, medications, and key patient context.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=400,  # Very short executive summary
            )

            summary = response.choices[0].message.content

            # Save the summary to cache
            patient.ai_summary = summary
            patient.ai_summary_updated_at = timezone.now()
            patient.save(update_fields=["ai_summary", "ai_summary_updated_at"])

            return Response(
                {
                    "summary": summary,
                    "model": "gpt-4o-mini",
                    "cached": False,
                }
            )

        except Exception as e:
            return Response(
                {"error": f"Failed to generate AI summary: {str(e)}"},
                status=500,
            )
