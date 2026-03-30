import pytest
from django.utils import timezone

from apps.scheduling.models import Appointment


@pytest.mark.django_db
def test_portal_booking_metrics_counts(api_client, clinic, patient, doctor):
    today = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
    Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=today,
        ends_at=today.replace(minute=30),
        status=Appointment.Status.CONFIRMED,
        reason="In-app",
        booked_via_portal=False,
    )
    Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=today.replace(hour=11),
        ends_at=today.replace(hour=11, minute=30),
        status=Appointment.Status.CONFIRMED,
        reason="Portal",
        booked_via_portal=True,
    )

    api_client.force_authenticate(user=doctor)
    day = today.date().isoformat()
    r = api_client.get(
        "/api/reports/portal-booking-metrics/",
        {"from": day, "to": day},
    )
    assert r.status_code == 200
    assert r.data["appointments_total"] == 2
    assert r.data["appointments_booked_via_portal"] == 1
    assert r.data["share_portal"] == 0.5
