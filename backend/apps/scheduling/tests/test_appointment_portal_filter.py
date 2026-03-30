from datetime import timedelta

import pytest
from apps.scheduling.models import Appointment
from django.utils import timezone


@pytest.mark.django_db
def test_list_appointments_filter_booked_via_portal(
    api_client, receptionist, doctor, patient, clinic
):
    starts = timezone.now() + timedelta(days=1)
    ends = starts + timedelta(minutes=30)
    portal_appt = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=starts,
        ends_at=ends,
        status=Appointment.Status.CONFIRMED,
        booked_via_portal=True,
    )
    staff_appt = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=starts + timedelta(hours=2),
        ends_at=ends + timedelta(hours=2),
        status=Appointment.Status.CONFIRMED,
        booked_via_portal=False,
    )

    api_client.force_authenticate(user=receptionist)
    r_true = api_client.get("/api/appointments/", {"booked_via_portal": "true"})
    assert r_true.status_code == 200
    ids_true = {row["id"] for row in r_true.data}
    assert portal_appt.id in ids_true
    assert staff_appt.id not in ids_true

    r_false = api_client.get("/api/appointments/", {"booked_via_portal": "false"})
    assert r_false.status_code == 200
    ids_false = {row["id"] for row in r_false.data}
    assert staff_appt.id in ids_false
    assert portal_appt.id not in ids_false
