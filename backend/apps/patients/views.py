import os

from django.conf import settings
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin, IsStaffOrVet
from apps.billing.models import Invoice
from apps.billing.serializers import InvoiceReadSerializer
from apps.billing.services.recent_supply_lines import recent_supply_line_suggestions
from apps.clients.models import ClientClinic
from apps.medical.models import MedicalRecord, PatientHistoryEntry, Prescription, Vaccination
from apps.medical.serializers import (
    MedicalRecordReadSerializer,
    PatientHistoryEntryWriteSerializer,
    PrescriptionReadSerializer,
    PrescriptionWriteSerializer,
    VaccinationReadSerializer,
    VaccinationWriteSerializer,
)
from apps.patients.models import Patient
from apps.patients.serializers import (
    ClientMiniSerializer,
    PatientHistoryForPatientSerializer,
    PatientReadSerializer,
    PatientWriteSerializer,
)
from apps.scheduling.models import Appointment
from apps.scheduling.serializers import AppointmentReadSerializer
from apps.tenancy.access import (
    accessible_clinic_ids,
    clinic_instance_for_mutation,
    user_can_access_clinic,
)


class PatientViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic]

    @action(
        detail=True,
        methods=["get"],
        url_path="last-vitals",
        permission_classes=[IsStaffOrVet],
    )
    def last_vitals(self, request, pk=None):
        patient = self.get_object()
        exam = (
            Appointment.objects.filter(clinic_id=request.user.clinic_id, patient_id=patient.id)
            .select_related("clinical_exam")
            .exclude(clinical_exam__isnull=True)
            .order_by("-starts_at", "-id")
            .first()
        )
        if not exam or not getattr(exam, "clinical_exam", None):
            return Response(status=204)
        clinical_exam = exam.clinical_exam
        payload = {
            "temperature_c": (
                str(clinical_exam.temperature_c)
                if clinical_exam.temperature_c is not None
                else None
            ),
            "heart_rate_bpm": clinical_exam.heart_rate_bpm,
            "respiratory_rate_rpm": clinical_exam.respiratory_rate_rpm,
            "weight_kg": (
                str(clinical_exam.weight_kg) if clinical_exam.weight_kg is not None else None
            ),
            "recorded_at": clinical_exam.created_at.isoformat(),
        }
        return Response(payload, status=200)

    @action(
        detail=True,
        methods=["get"],
        url_path="recent-supply-lines",
        permission_classes=[IsStaffOrVet],
    )
    def recent_supply_lines(self, request, pk=None):
        patient = self.get_object()
        raw_limit = request.query_params.get("limit", "20")
        try:
            limit_n = int(raw_limit)
        except (TypeError, ValueError):
            raise ValidationError({"limit": "Must be a positive integer."}) from None
        limit_n = max(1, min(limit_n, 50))
        data = recent_supply_line_suggestions(
            clinic_id__in=accessible_clinic_ids(request.user),
            patient_id=patient.id,
            limit=limit_n,
        )
        return Response(data, status=200)

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="prescriptions",
        permission_classes=[IsStaffOrVet],
    )
    def prescriptions(self, request, pk=None):
        """
        GET  /api/patients/<id>/prescriptions/  -> list prescriptions (clinic scoped)
        POST /api/patients/<id>/prescriptions/  -> create (doctors and admins only)
        """
        user = request.user
        patient = self.get_object()

        if request.method == "GET":
            qs = Prescription.objects.filter(
                clinic_id__in=accessible_clinic_ids(user),
                patient_id=patient.id,
            ).order_by("-created_at")
            return Response(PrescriptionReadSerializer(qs, many=True).data, status=200)

        # POST: only doctors and admins
        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can create prescriptions.")
        if not getattr(user, "clinic_id", None):
            raise ValidationError("User must belong to a clinic to create prescriptions.")
        serializer = PrescriptionWriteSerializer(
            data=request.data,
            context={"request": request, "patient": patient},
        )
        serializer.is_valid(raise_exception=True)
        prescription = Prescription.objects.create(
            clinic_id__in=accessible_clinic_ids(user),
            patient=patient,
            prescribed_by=user,
            **serializer.validated_data,
        )
        return Response(
            PrescriptionReadSerializer(prescription).data,
            status=201,
        )

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="vaccinations",
        permission_classes=[IsStaffOrVet],
    )
    def vaccinations(self, request, pk=None):
        """
        GET  /api/patients/<id>/vaccinations/  -> list vaccinations for this patient (clinic scoped)
        POST /api/patients/<id>/vaccinations/  -> record new vaccination
        """
        user = request.user
        patient = self.get_object()

        if request.method == "GET":
            qs = Vaccination.objects.filter(
                clinic_id__in=accessible_clinic_ids(user),
                patient_id=patient.id,
            ).order_by("-administered_at")
            if request.query_params.get("upcoming") == "1":
                qs = qs.filter(
                    next_due_at__isnull=False,
                    next_due_at__gte=timezone.now().date(),
                )
            return Response(VaccinationReadSerializer(qs, many=True).data, status=200)

        # POST: create new vaccination
        if not getattr(user, "clinic_id", None):
            raise ValidationError("User must belong to a clinic to record vaccinations.")
        serializer = VaccinationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vaccination = Vaccination.objects.create(
            clinic_id__in=accessible_clinic_ids(user),
            patient=patient,
            administered_by=user,
            **serializer.validated_data,
        )
        return Response(
            VaccinationReadSerializer(vaccination).data,
            status=201,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="profile",
        permission_classes=[IsStaffOrVet],
    )
    def profile(self, request, pk=None):
        """
        GET /api/patients/<id>/profile/
        Single-call payload: patient, owner, last 5 medical records, all vaccinations,
        next 3 upcoming appointments, open invoices. Clinic-scoped.
        """
        patient = self.get_object()
        user = request.user
        now = timezone.now()
        open_statuses = [
            Invoice.Status.DRAFT,
            Invoice.Status.SENT,
            Invoice.Status.OVERDUE,
        ]
        upcoming_statuses = [
            Appointment.Status.SCHEDULED,
            Appointment.Status.CONFIRMED,
            Appointment.Status.CHECKED_IN,
        ]

        patient = (
            Patient.objects.filter(pk=patient.pk, clinic_id__in=accessible_clinic_ids(user))
            .select_related("owner", "primary_vet", "clinic")
            .prefetch_related(
                Prefetch(
                    "medical_records",
                    queryset=MedicalRecord.objects.select_related("created_by").order_by(
                        "-created_at"
                    ),
                ),
                Prefetch(
                    "vaccinations",
                    queryset=Vaccination.objects.select_related("administered_by").order_by(
                        "-administered_at"
                    ),
                ),
                Prefetch(
                    "appointments",
                    queryset=Appointment.objects.filter(
                        starts_at__gte=now, status__in=upcoming_statuses
                    )
                    .select_related("vet", "room")
                    .order_by("starts_at"),
                ),
                Prefetch(
                    "invoices",
                    queryset=Invoice.objects.filter(status__in=open_statuses)
                    .select_related("client", "patient")
                    .prefetch_related("lines", "payments")
                    .order_by("-created_at"),
                ),
            )
            .first()
        )
        if not patient:
            raise NotFound()

        medical_records = list(patient.medical_records.all())[:5]
        vaccinations = list(patient.vaccinations.all())
        upcoming_appointments = list(patient.appointments.all())[:3]
        open_invoices = list(patient.invoices.all())

        data = {
            "patient": PatientReadSerializer(patient).data,
            "owner": ClientMiniSerializer(patient.owner).data,
            "medical_records": MedicalRecordReadSerializer(medical_records, many=True).data,
            "vaccinations": VaccinationReadSerializer(vaccinations, many=True).data,
            "upcoming_appointments": AppointmentReadSerializer(
                upcoming_appointments, many=True
            ).data,
            "open_invoices": InvoiceReadSerializer(open_invoices, many=True).data,
        }
        return Response(data, status=200)

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return PatientReadSerializer
        return PatientWriteSerializer

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            return Patient.objects.none()

        qs = Patient.objects.filter(clinic_id__in=accessible_clinic_ids(user)).select_related(
            "owner",
            "primary_vet",
            "clinic",
        )

        # Search across patient name, microchip, owner name, surname, and phone
        search = self.request.query_params.get("search")
        if search:
            search = search.strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(microchip_no__icontains=search)
                | Q(owner__first_name__icontains=search)
                | Q(owner__last_name__icontains=search)
                | Q(owner__phone__icontains=search)
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
        if not accessible_clinic_ids(user):
            raise ValidationError("No clinic access to create patients.")

        clinic = clinic_instance_for_mutation(user, self.request)
        patient = serializer.save(clinic=clinic)

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

        if instance.clinic_id and not user_can_access_clinic(user, instance.clinic_id):
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
                    clinic_id__in=accessible_clinic_ids(user),
                    record__patient_id=patient.id,
                )
                .select_related("record", "created_by", "appointment", "invoice")
                .prefetch_related("invoice__lines")
                .order_by("-created_at")
            )
            return Response(PatientHistoryForPatientSerializer(qs, many=True).data)

        # POST requires doctor or clinic admin
        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can add history notes.")

        # PatientHistoryEntry uses record (MedicalRecord), not patient_id. Get or create MedicalRecord.
        record, _ = MedicalRecord.objects.get_or_create(
            clinic_id__in=accessible_clinic_ids(user),
            patient_id=patient.id,
            defaults={"created_by": user},
        )

        serializer = PatientHistoryEntryWriteSerializer(
            data={
                "record": record.id,
                "note": request.data.get("note", ""),
                "invoice": request.data.get("invoice"),
                "appointment": request.data.get("appointment"),
            },
            context={"request": request, "patient": patient},
        )
        serializer.is_valid(raise_exception=True)
        if not (serializer.validated_data.get("note") or "").strip():
            raise ValidationError({"note": "Note is required."})

        entry = serializer.save(
            clinic_id__in=accessible_clinic_ids(user),
            created_by=user,
        )

        # Invalidate AI summary cache when a new history entry is added
        patient.ai_summary = ""
        patient.ai_summary_updated_at = None
        patient.save(update_fields=["ai_summary", "ai_summary_updated_at"])

        entry = (
            PatientHistoryEntry.objects.filter(pk=entry.pk)
            .select_related("record", "created_by", "appointment", "invoice")
            .prefetch_related("invoice__lines")
            .get()
        )
        return Response(PatientHistoryForPatientSerializer(entry).data, status=201)

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
                clinic_id__in=accessible_clinic_ids(user),
                record__patient_id=patient.id,
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
                clinic_id__in=accessible_clinic_ids(user),
                record__patient_id=patient.id,
            )
            .select_related("record", "created_by")
            .order_by("-created_at")
        )

        history_data = []
        for entry in history_entries:
            history_item = {
                "date": str(entry.created_at.date()),
                "note": entry.note,
                "receipt_summary": "",
            }
            history_data.append(history_item)

        # Collect appointments
        appointments = Appointment.objects.filter(
            clinic_id__in=accessible_clinic_ids(user),
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

        # Collect medical records (SOAP notes) - MedicalRecord has patient, not appointment
        medical_records = (
            MedicalRecord.objects.filter(
                clinic_id__in=accessible_clinic_ids(user),
                patient_id=patient.id,
            )
            .select_related("created_by")
            .order_by("-created_at")
        )

        medical_records_data = []
        for record in medical_records[:10]:  # Limit to last 10
            medical_records_data.append(
                {
                    "date": str(record.created_at.date()),
                    "subjective": "",
                    "objective": "",
                    "assessment": record.ai_summary or "",
                    "plan": "",
                    "weight_kg": None,
                    "temperature_c": None,
                }
            )

        # If there's no history data at all, return a simple message
        if not history_data and not appointments_data and not medical_records_data:
            summary = "No visit history for this patient."
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

        # Build focused prompt for executive summary using ONLY the provided data
        prompt = "Create a brief executive summary for a veterinarian based ONLY on the provided visit history data below. Use ONLY the information provided - do not infer, assume, or add any information not explicitly stated in the data.\n\n"
        prompt += "Include:\n"
        prompt += "1. Key medical history and notable events from the visit notes\n"
        prompt += "2. Current medications and prescriptions mentioned in the visit notes\n"
        prompt += "3. Important context from the visit history\n\n"

        # Add allergies if present (critical information)
        if patient.allergies:
            prompt += f"ALLERGIES: {patient.allergies}\n\n"

        # Extract medications from visit history, receipts, and medical records
        # Collect visit history
        if history_data:
            prompt += f"Visit History ({len(history_data)} visits):\n"
            for entry in history_data[:15]:  # Limit to last 15 for more context
                prompt += f"- Date: {entry['date']}\n"
                prompt += f"  Notes: {entry['note']}\n"
                if entry["receipt_summary"]:
                    prompt += f"  Medications/Treatment: {entry['receipt_summary']}\n"
                if entry.get("appointment_reason"):
                    prompt += f"  Reason: {entry['appointment_reason']}\n"
                prompt += "\n"

        # Add medical records (focus on plan/medications)
        if medical_records_data:
            prompt += f"\nMedical Records ({len(medical_records_data)} records):\n"
            for record in medical_records_data[:10]:  # Limit to last 10
                prompt += f"- Date: {record['date']}\n"
                if record["assessment"]:
                    prompt += f"  Assessment: {record['assessment']}\n"
                if record["plan"]:
                    prompt += f"  Plan: {record['plan']}\n"
                prompt += "\n"

        prompt += "\nIMPORTANT: Base your summary ONLY on the visit history and medical records provided above. Do not include any information that is not explicitly mentioned in the data. If no medications are mentioned, do not mention medications. If no specific conditions are mentioned, do not infer conditions. Be factual and concise (1-2 short paragraphs)."

        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a veterinary assistant creating factual executive summaries. You MUST use ONLY the information explicitly provided in the visit history and medical records. Do NOT infer, assume, or add any information that is not directly stated in the provided data. Do NOT include patient name, species, or breed. If information is not provided, do not make it up. Be concise, factual, and focus only on what is explicitly documented.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,  # Lower temperature for more factual, less creative output
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

        except Exception:
            return Response(
                {
                    "code": "ai_summary_generation_failed",
                    "message": "Failed to generate AI summary.",
                },
                status=500,
            )
