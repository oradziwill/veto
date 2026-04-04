"""Step definitions for inventory barcode BDD features."""

from apps.accounts.models import User
from apps.tenancy.models import Clinic
from behave import given, then, when
from django.urls import reverse


@given("a clinic with a vet for inventory")
def step_clinic_vet_inventory(context):
    context.clinic = Clinic.objects.create(
        name="Behave Inv Clinic",
        address="1 Test St",
        phone="+1000000001",
        email="behave-inv@test.local",
    )
    context.vet = User.objects.create_user(
        username="behave_inv_vet",
        password="testpass123",
        clinic=context.clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )


@when("I request inventory resolve_barcode without auth")
def step_resolve_no_auth(context):
    url = reverse("inventory-items-resolve-barcode")
    context.last_response = context.api.get(url, {"code": "5901234123457"})


@when('the vet creates an inventory item with barcode "{barcode}"')
def step_vet_create_item_barcode(context, barcode):
    context.api.force_authenticate(user=context.vet)
    url = reverse("inventory-items-list")
    context.last_response = context.api.post(
        url,
        {
            "name": "Behave Drug",
            "sku": "BEHAVE_SKU",
            "barcode": barcode,
            "category": "medication",
            "unit": "pcs",
            "stock_on_hand": 0,
            "low_stock_threshold": 0,
        },
        format="json",
    )


@when('the vet posts inventory line barcode "{barcode}" sku "{sku}"')
def step_vet_post_line_barcode_sku(context, barcode, sku):
    context.api.force_authenticate(user=context.vet)
    url = reverse("inventory-items-list")
    context.last_response = context.api.post(
        url,
        {
            "name": f"Item {sku}",
            "sku": sku,
            "barcode": barcode,
            "category": "medication",
            "unit": "pcs",
            "stock_on_hand": 0,
            "low_stock_threshold": 0,
        },
        format="json",
    )


@when('the vet resolves barcode "{barcode}"')
def step_vet_resolve(context, barcode):
    context.api.force_authenticate(user=context.vet)
    url = reverse("inventory-items-resolve-barcode")
    context.last_response = context.api.get(url, {"code": barcode})


@then('the resolved item has barcode "{barcode}"')
def step_resolved_barcode(context, barcode):
    data = context.last_response.data
    assert data.get("barcode") == barcode, data
