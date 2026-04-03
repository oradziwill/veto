"""BDD steps for lab integration ingest."""

import json

from apps.accounts.models import User
from apps.clients.models import Client
from apps.labs.models import (
    Lab,
    LabExternalIdentifier,
    LabIngestionEnvelope,
    LabIntegrationDevice,
    LabObservation,
    LabOrder,
    LabOrderLine,
    LabResult,
    LabResultComponent,
    LabSample,
    LabTest,
    LabTestCodeMap,
)
from apps.patients.models import Patient
from apps.tenancy.models import Clinic
from behave import given, then, when
from django.urls import reverse


@given('a clinic lab ingest setup with three tests and barcode "{barcode}"')
def step_lab_setup_three(context, barcode):
    _lab_ingest_base_setup(context, barcode=barcode, num_tests=3)


@given('a clinic lab ingest setup with one test and barcode "{barcode}"')
def step_lab_setup_one(context, barcode):
    _lab_ingest_base_setup(context, barcode=barcode, num_tests=1)


def _lab_ingest_base_setup(context, *, barcode: str, num_tests: int):
    context.clinic = Clinic.objects.create(
        name="Lab Behave Clinic",
        address="2 Test St",
        phone="+1000000001",
        email="labbehave@test.local",
    )
    context.doctor = User.objects.create_user(
        username="lab_behave_doctor",
        password="testpass123",
        clinic=context.clinic,
        is_staff=True,
        role=User.Role.DOCTOR,
    )
    client = Client.objects.create(first_name="Lab", last_name="Owner")
    context.patient = Patient.objects.create(
        clinic=context.clinic,
        owner=client,
        name="Test Pet",
        species="canine",
    )
    context.lab = Lab.objects.create(
        clinic=context.clinic, name="In-house Lab", lab_type=Lab.LabType.IN_CLINIC
    )
    context.tests = []
    codes = ["GLU", "ALT", "ALP"][:num_tests]
    for code in codes:
        t = LabTest.objects.create(lab=context.lab, code=code, name=f"Test {code}")
        context.tests.append(t)
    context.device = LabIntegrationDevice.objects.create(
        clinic=context.clinic,
        lab=context.lab,
        name="Behave Analyzer",
        connection_kind=LabIntegrationDevice.ConnectionKind.FILE_DROP,
        ingest_token="behave-ingest-secret",
    )
    for t in context.tests:
        LabTestCodeMap.objects.create(
            clinic=context.clinic,
            device=context.device,
            vendor_code=t.code,
            lab_test=t,
            priority=10,
        )
    context.order = LabOrder.objects.create(
        clinic=context.clinic,
        patient=context.patient,
        lab=context.lab,
        status=LabOrder.Status.SENT,
        ordered_by=context.doctor,
    )
    for t in context.tests:
        line = LabOrderLine.objects.create(order=context.order, test=t)
        LabResult.objects.create(order_line=line)
    context.sample = LabSample.objects.create(
        clinic=context.clinic,
        lab_order=context.order,
        internal_sample_code="SAMP-1",
        status=LabSample.SampleStatus.COLLECTED,
    )
    LabExternalIdentifier.objects.create(
        clinic=context.clinic,
        sample=context.sample,
        scheme="barcode",
        value=barcode,
    )
    context.barcode = barcode
    context.num_tests = num_tests
    observations = [
        {"vendor_code": "GLU", "value_numeric": "5.5", "unit": "mmol/L", "natural_key": "0"},
        {"vendor_code": "ALT", "value_numeric": "45", "unit": "U/L", "natural_key": "1"},
        {"vendor_code": "ALP", "value_numeric": "120", "unit": "U/L", "natural_key": "2"},
    ][:num_tests]
    context.ingest_payload = {
        "identifiers": [{"scheme": "barcode", "value": barcode}],
        "observations": observations,
    }


@when("I POST the same lab ingest payload twice")
def step_post_twice(context):
    url = reverse("lab-device-ingest", kwargs={"device_id": context.device.id})
    body = json.dumps(context.ingest_payload).encode("utf-8")
    context.api.credentials()
    context.last_response = context.api.post(
        url,
        data=body,
        content_type="application/json",
        HTTP_X_LAB_INGEST_TOKEN="behave-ingest-secret",
    )
    assert context.last_response.status_code == 201, context.last_response.content
    context.last_response = context.api.post(
        url,
        data=body,
        content_type="application/json",
        HTTP_X_LAB_INGEST_TOKEN="behave-ingest-secret",
    )


@then("the second response status is {status:d}")
def step_second_status(context, status):
    assert context.last_response.status_code == status, context.last_response.content


@then("only one lab ingestion envelope exists for that idempotency pattern")
def step_one_envelope(context):
    assert LabIngestionEnvelope.objects.filter(device=context.device).count() == 1


@then("the lab order has 3 result components")
def step_three_components(context):
    n = LabResultComponent.objects.filter(lab_result__order_line__order=context.order).count()
    assert n == 3, n


@when("I ingest observations without identifiers")
def step_ingest_no_id(context):
    payload = {
        "identifiers": [],
        "observations": [
            {
                "vendor_code": context.tests[0].code,
                "value_numeric": "9.9",
                "unit": "mmol/L",
                "natural_key": "x0",
            },
        ],
    }
    url = reverse("lab-device-ingest", kwargs={"device_id": context.device.id})
    context.api.credentials()
    context.last_response = context.api.post(
        url,
        data=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
        HTTP_X_LAB_INGEST_TOKEN="behave-ingest-secret",
    )
    assert context.last_response.status_code == 201, context.last_response.content
    context.unmatched_obs = LabObservation.objects.filter(
        envelope_id=context.last_response.data["id"]
    ).first()


@then('the observation has match_status "{ms}"')
def step_match_status(context, ms):
    obs = LabObservation.objects.filter(envelope_id=context.last_response.data["id"]).first()
    assert obs is not None
    assert obs.match_status == ms


@when("the doctor resolves the observation to the order line")
def step_resolve(context):
    context.api.force_authenticate(user=context.doctor)
    line = context.order.lines.first()
    url = reverse("lab-observations-resolve", kwargs={"pk": context.unmatched_obs.pk})
    context.last_response = context.api.post(url, {"lab_order_line_id": line.id}, format="json")


@then("the lab order line has a result component")
def step_line_has_component(context):
    line = context.order.lines.first()
    assert LabResultComponent.objects.filter(lab_result__order_line=line).exists()
