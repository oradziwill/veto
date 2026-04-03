from datetime import date

import pytest
from django.db import IntegrityError

from apps.tenancy.models import Clinic, ClinicHoliday, ClinicNetwork


@pytest.mark.django_db
def test_clinic_slug_is_generated_and_unique():
    first = Clinic.objects.create(name="Blue Paws Clinic")
    second = Clinic.objects.create(name="Blue Paws Clinic")
    assert first.slug == "blue-paws-clinic"
    assert second.slug.startswith("blue-paws-clinic-")
    assert first.slug != second.slug


@pytest.mark.django_db
def test_clinic_network_slug_is_generated_and_unique():
    first = ClinicNetwork.objects.create(name="Veto Chain")
    second = ClinicNetwork.objects.create(name="Veto Chain")
    assert first.slug == "veto-chain"
    assert second.slug.startswith("veto-chain-")
    assert first.slug != second.slug


@pytest.mark.django_db
def test_clinic_can_belong_to_network():
    net = ClinicNetwork.objects.create(name="Net A")
    clinic = Clinic.objects.create(name="Clinic One", network=net)
    clinic.refresh_from_db()
    assert clinic.network_id == net.id
    assert list(net.clinics.all()) == [clinic]


@pytest.mark.django_db
def test_clinic_holiday_unique_for_clinic_and_date():
    clinic = Clinic.objects.create(
        name="Test Clinic",
        address="Street 1",
        phone="+48123123123",
        email="test@clinic.com",
    )
    closure_day = date(2026, 3, 11)
    ClinicHoliday.objects.create(clinic=clinic, date=closure_day, reason="Holiday")

    with pytest.raises(IntegrityError):
        ClinicHoliday.objects.create(clinic=clinic, date=closure_day, reason="Duplicate")
