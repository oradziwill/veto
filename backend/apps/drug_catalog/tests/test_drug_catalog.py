from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.drug_catalog.models import ClinicProductMapping, ReferenceProduct
from apps.inventory.models import InventoryItem
from apps.tenancy.models import Clinic


@pytest.mark.django_db
def test_drug_catalog_search_requires_auth():
    client = APIClient()
    url = reverse("drug-catalog-search")
    resp = client.get(url)
    assert resp.status_code == 401


@pytest.mark.django_db
def test_drug_catalog_search_filters_by_q():
    clinic = Clinic.objects.create(name="C", address="a", phone="p", email="e@e.com")
    vet = User.objects.create_user(
        username="vet_dc",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )
    ReferenceProduct.objects.create(
        external_source=ReferenceProduct.ExternalSource.MANUAL,
        external_id="manual-test-1",
        name="Amoxicillin Tablets",
        common_name="Amoxicillin",
    )
    ReferenceProduct.objects.create(
        external_source=ReferenceProduct.ExternalSource.MANUAL,
        external_id="manual-test-2",
        name="Other",
        common_name="",
    )

    client = APIClient()
    client.force_authenticate(user=vet)
    url = reverse("drug-catalog-search")
    resp = client.get(url, {"q": "Amox"})
    assert resp.status_code == 200
    data = resp.data
    assert "results" in data or isinstance(data, list)
    results = data.get("results", data)
    names = {r["name"] for r in results}
    assert "Amoxicillin Tablets" in names
    assert "Other" not in names


@pytest.mark.django_db
def test_clinic_mapping_create():
    clinic = Clinic.objects.create(name="C", address="a", phone="p", email="e@e.com")
    vet = User.objects.create_user(
        username="vet_map",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )
    inv = InventoryItem.objects.create(
        clinic=clinic,
        name="Box A",
        sku="SKU-1",
        unit="box",
        created_by=vet,
    )
    ref = ReferenceProduct.objects.create(
        external_source=ReferenceProduct.ExternalSource.MANUAL,
        external_id="m-2",
        name="Ref drug",
    )
    client = APIClient()
    client.force_authenticate(user=vet)
    url = reverse("drug-catalog-mappings-list")
    resp = client.post(
        url,
        {
            "inventory_item": inv.id,
            "reference_product": ref.id,
            "local_alias": "alias",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert ClinicProductMapping.objects.filter(clinic=clinic, inventory_item=inv).exists()


@pytest.mark.django_db
def test_sync_drug_catalog_no_ema_base_url():
    from apps.drug_catalog.models import SyncRun

    call_command("sync_drug_catalog")
    run = SyncRun.objects.order_by("-id").first()
    assert run is not None
    assert run.status == SyncRun.Status.SUCCESS
    assert run.records_processed == 0


@pytest.mark.django_db
def test_run_ema_sync_with_mocked_rows(settings):
    settings.EMA_UPD_BASE_URL = "https://example.test"
    settings.EMA_UPD_PRODUCTS_PATH = "/products"

    fake_rows = [
        {
            "external_id": "ema-1",
            "name": "Test Product",
            "common_name": "TP",
            "payload": {"species": ["dog"]},
        }
    ]
    with patch(
        "apps.drug_catalog.services.ema_upd.iter_product_candidates", return_value=fake_rows
    ):
        from apps.drug_catalog.services.sync import run_ema_sync

        n, detail = run_ema_sync(incremental=False)
    assert n == 1
    assert ReferenceProduct.objects.filter(external_id="ema-1").exists()
    assert detail["remote_rows"] == 1


@pytest.mark.django_db
def test_prescription_accepts_reference_product(patient, doctor):
    ref = ReferenceProduct.objects.create(
        external_source=ReferenceProduct.ExternalSource.MANUAL,
        external_id="rx-ref-1",
        name="Catalog Drug",
    )
    client = APIClient()
    client.force_authenticate(user=doctor)
    url = reverse("patients-prescriptions", args=[patient.id])
    resp = client.post(
        url,
        {
            "drug_name": "Catalog Drug",
            "dosage": "1 tab",
            "reference_product": ref.id,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["reference_product"]["id"] == ref.id
    assert resp.data["drug_name"] == "Catalog Drug"


@pytest.mark.django_db
def test_create_manual_reference_product_as_doctor(doctor):
    client = APIClient()
    client.force_authenticate(user=doctor)
    url = reverse("drug-catalog-products-list")
    resp = client.post(
        url,
        {"name": "My clinic drug", "common_name": "MCD", "payload": {"note": "internal"}},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["external_source"] == ReferenceProduct.ExternalSource.MANUAL
    assert resp.data["name"] == "My clinic drug"
    assert resp.data["external_id"].startswith("manual-")


@pytest.mark.django_db
def test_create_manual_reference_product_forbidden_for_receptionist(receptionist):
    client = APIClient()
    client.force_authenticate(user=receptionist)
    url = reverse("drug-catalog-products-list")
    resp = client.post(
        url,
        {"name": "X"},
        format="json",
    )
    assert resp.status_code == 403
