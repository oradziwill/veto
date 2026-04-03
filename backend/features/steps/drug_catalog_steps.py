"""Step definitions for drug catalog BDD features."""

from apps.accounts.models import User
from apps.tenancy.models import Clinic
from behave import given, then, when
from django.urls import reverse


@given("a clinic with a doctor and a receptionist")
def step_clinic_doctor_and_receptionist(context):
    context.clinic = Clinic.objects.create(
        name="Behave Clinic",
        address="1 Test St",
        phone="+1000000000",
        email="behave@test.local",
    )
    context.doctor = User.objects.create_user(
        username="behave_doctor",
        password="testpass123",
        clinic=context.clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )
    context.receptionist = User.objects.create_user(
        username="behave_receptionist",
        password="testpass123",
        clinic=context.clinic,
        role=User.Role.RECEPTIONIST,
    )


@when("I request drug catalog search without auth")
def step_search_no_auth(context):
    url = reverse("drug-catalog-search")
    context.last_response = context.api.get(url)


@when('the doctor searches the catalog for "{q}"')
def step_doctor_search(context, q):
    context.api.force_authenticate(user=context.doctor)
    url = reverse("drug-catalog-search")
    context.last_response = context.api.get(url, {"q": q})


@when('the doctor creates a manual reference product "{name}"')
def step_doctor_create_manual(context, name):
    context.api.force_authenticate(user=context.doctor)
    url = reverse("drug-catalog-products-list")
    context.last_response = context.api.post(
        url,
        {"name": name, "common_name": "BTD", "payload": {"source": "behave"}},
        format="json",
    )


@when('the receptionist creates a manual reference product "{name}"')
def step_receptionist_create_manual(context, name):
    context.api.force_authenticate(user=context.receptionist)
    url = reverse("drug-catalog-products-list")
    context.last_response = context.api.post(
        url,
        {"name": name},
        format="json",
    )


@then("the response status is {status:d}")
def step_response_status(context, status):
    assert context.last_response is not None
    assert context.last_response.status_code == status, (
        f"expected {status}, got {context.last_response.status_code}: "
        f"{getattr(context.last_response, 'data', context.last_response.content)}"
    )


@then('the search results contain "{name}"')
def step_search_contains_name(context, name):
    data = context.last_response.data
    results = data.get("results", data) if isinstance(data, dict) else data
    if isinstance(results, dict):
        results = results.get("results", [])
    names = {row.get("name") for row in results if isinstance(row, dict)}
    assert name in names, f"{name!r} not in {names}"
