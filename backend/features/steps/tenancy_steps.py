"""Step definitions for clinic network / tenancy Behave features."""

from apps.accounts.models import User
from apps.tenancy.models import Clinic, ClinicNetwork
from behave import given, then, when
from django.urls import reverse


@given("a network with two clinics each having one vet")
def step_network_two_clinics_two_vets(context):
    net = ClinicNetwork.objects.create(name="Behave Tenancy Net")
    context.network = net
    context.clinic_a = Clinic.objects.create(
        name="Behave Clinic A",
        network=net,
        address="1 A St",
        phone="+1000000001",
        email="clinic_a@behave.test",
    )
    context.clinic_b = Clinic.objects.create(
        name="Behave Clinic B",
        network=net,
        address="2 B St",
        phone="+1000000002",
        email="clinic_b@behave.test",
    )
    context.vet_a = User.objects.create_user(
        username="behave_vet_clinic_a",
        password="testpass123",
        clinic=context.clinic_a,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )
    context.vet_b = User.objects.create_user(
        username="behave_vet_clinic_b",
        password="testpass123",
        clinic=context.clinic_b,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )


@given("a network admin for that network without a clinic membership")
def step_network_admin(context):
    context.network_admin = User.objects.create_user(
        username="behave_network_admin",
        password="testpass123",
        role=User.Role.NETWORK_ADMIN,
        network=context.network,
        is_staff=True,
        clinic=None,
    )


@given("a standalone clinic with one vet")
def step_standalone_clinic_vet(context):
    context.clinic = Clinic.objects.create(
        name="Behave Standalone Clinic",
        address="9 Solo St",
        phone="+1000000099",
        email="solo@behave.test",
    )
    context.doctor = User.objects.create_user(
        username="behave_standalone_vet",
        password="testpass123",
        clinic=context.clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )


@when("I request me without authentication")
def step_me_no_auth(context):
    context.last_response = context.api.get(reverse("me"))


@when("the network admin requests me")
def step_network_admin_me(context):
    context.api.force_authenticate(user=context.network_admin)
    context.last_response = context.api.get(reverse("me"))


@when("the vet from clinic A requests me")
def step_vet_a_me(context):
    context.api.force_authenticate(user=context.vet_a)
    context.last_response = context.api.get(reverse("me"))


@when("the standalone vet requests me")
def step_standalone_me(context):
    context.api.force_authenticate(user=context.doctor)
    context.last_response = context.api.get(reverse("me"))


@when("the network admin lists vets")
def step_network_admin_list_vets(context):
    context.api.force_authenticate(user=context.network_admin)
    context.last_response = context.api.get(reverse("vets-list"))


@when("the vet from clinic A lists vets")
def step_vet_a_list_vets(context):
    context.api.force_authenticate(user=context.vet_a)
    context.last_response = context.api.get(reverse("vets-list"))


@then('the me payload has role "{role}"')
def step_me_role(context, role):
    data = context.last_response.data
    assert data.get("role") == role, f"expected role {role!r}, got {data!r}"


@then("the me payload includes a network reference")
def step_me_has_network(context):
    data = context.last_response.data
    assert data.get("network") is not None, f"expected network on me payload, got {data!r}"


@then("the me payload includes the user clinic id")
def step_me_has_clinic(context):
    data = context.last_response.data
    assert data.get("clinic") == context.doctor.clinic_id


@then('the vets list includes usernames "{u1}" and "{u2}"')
def step_vets_includes_both(context, u1, u2):
    data = context.last_response.data
    assert isinstance(data, list), f"expected list, got {type(data)}: {data!r}"
    names = {row.get("username") for row in data if isinstance(row, dict)}
    assert u1 in names and u2 in names, f"expected {u1!r} and {u2!r} in {names}"


@then('the vets list does not include username "{u}"')
def step_vets_excludes(context, u):
    data = context.last_response.data
    assert isinstance(data, list), f"expected list, got {type(data)}: {data!r}"
    names = {row.get("username") for row in data if isinstance(row, dict)}
    assert u not in names, f"did not expect {u!r} in {names}"
