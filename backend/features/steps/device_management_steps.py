"""BDD steps for device management + fiscal queue workflow."""

from apps.accounts.models import User
from apps.device_management.models import AgentNode, Device, DeviceCommand, FiscalReceipt
from apps.tenancy.models import Clinic
from behave import given, then, when


@given("a clinic device management setup with one fiscal device")
def step_setup_dm(context):
    context.clinic = Clinic.objects.create(
        name="DM Behave Clinic",
        address="3 Test St",
        phone="+1000000003",
        email="dmbehave@test.local",
    )
    context.admin = User.objects.create_user(
        username="dm_behave_admin",
        password="testpass123",
        clinic=context.clinic,
        is_staff=True,
        role=User.Role.ADMIN,
    )
    context.api.force_authenticate(user=context.admin)
    context.fiscal_device = Device.objects.create(
        clinic=context.clinic,
        device_type=Device.DeviceType.FISCAL,
        lifecycle_state=Device.LifecycleState.ACTIVE,
        name="ELZAB Front Desk",
        vendor="ELZAB",
        model="Mock",
        external_ref="fiscal:elzab-frontdesk",
        connection_type="serial",
        connection_config={"port": "/dev/ttyUSB0"},
    )
    context.agent_node_id = "behave-agent-1"
    context.last_response = None
    context.last_command = None
    context.receipt = None
    context.initial_idempotency_key = None


@when("the agent registers itself")
def step_agent_register(context):
    context.api.force_authenticate(user=context.admin)
    context.last_response = context.api.post(
        "/api/device-management/agents/register/",
        {
            "clinic_id": context.clinic.id,
            "node_id": context.agent_node_id,
            "name": "Behave Agent",
            "version": "0.1.0",
            "host": "127.0.0.1",
        },
        format="json",
    )
    assert context.last_response.status_code == 201, context.last_response.content
    assert AgentNode.objects.filter(clinic=context.clinic, node_id=context.agent_node_id).exists()


@when("an admin creates a fiscal receipt")
def step_create_receipt(context):
    context.api.force_authenticate(user=context.admin)
    payload = {
        "device": context.fiscal_device.id,
        "sale_ref": "SALE-123",
        "buyer_tax_id": "1234567890",
        "gross_total": "250.00",
        "currency": "PLN",
        "payload": {
            "receipt_id": "R-1",
            "items": [
                {
                    "name": "Konsultacja",
                    "quantity": 1,
                    "unit": "szt",
                    "unit_price_gross": "250.00",
                    "vat_rate": "23",
                }
            ],
            "payments": [{"method": "card", "amount": "250.00"}],
            "total_gross": "250.00",
        },
    }
    context.last_response = context.api.post("/api/fiscal/receipts/", payload, format="json")
    assert context.last_response.status_code == 201, context.last_response.content
    context.receipt = FiscalReceipt.objects.get(pk=context.last_response.data["id"])
    context.initial_idempotency_key = str(context.receipt.idempotency_key)


@then('receipt status is "{expected_status}"')
def step_receipt_status(context, expected_status):
    context.receipt.refresh_from_db()
    assert context.receipt.status == expected_status


@then("one pending fiscal_print command exists for this receipt")
def step_pending_command_exists(context):
    cmd = DeviceCommand.objects.filter(
        clinic=context.clinic,
        command_type="fiscal_print",
        payload__receipt_pk=context.receipt.id,
        status=DeviceCommand.CommandStatus.PENDING,
    ).first()
    assert cmd is not None
    context.last_command = cmd


@when("the agent pulls pending commands")
def step_pull_commands(context):
    context.api.force_authenticate(user=context.admin)
    context.last_response = context.api.get(
        "/api/device-management/agent/commands/",
        {"node_id": context.agent_node_id, "clinic_id": context.clinic.id},
    )
    assert context.last_response.status_code == 200, context.last_response.content
    data = context.last_response.data
    assert len(data) >= 1
    context.pulled_command = data[0]


@then('the pulled command type is "{command_type}"')
def step_pulled_command_type(context, command_type):
    assert context.pulled_command["command_type"] == command_type


@when('the agent reports command success with fiscal number "{fiscal_number}"')
def step_report_success(context, fiscal_number):
    context.api.force_authenticate(user=context.admin)
    context.last_response = context.api.post(
        f"/api/device-management/agent/commands/{context.pulled_command['id']}/result/",
        {
            "status": "succeeded",
            "result_payload": {"fiscal_number": fiscal_number, "message": "printed"},
            "error_message": "",
        },
        format="json",
    )
    assert context.last_response.status_code == 200, context.last_response.content


@then('receipt has {count:d} print attempt with status "{attempt_status}"')
def step_attempt_count_status(context, count, attempt_status):
    context.receipt.refresh_from_db()
    attempts = context.receipt.attempts.filter(status=attempt_status)
    assert attempts.count() == count


@when('the agent reports command failure "{error_message}"')
def step_report_failure(context, error_message):
    context.api.force_authenticate(user=context.admin)
    context.last_response = context.api.post(
        f"/api/device-management/agent/commands/{context.pulled_command['id']}/result/",
        {
            "status": "failed",
            "result_payload": {"message": error_message},
            "error_message": error_message,
        },
        format="json",
    )
    assert context.last_response.status_code == 200, context.last_response.content


@when("admin retries the fiscal receipt")
def step_retry_receipt(context):
    context.api.force_authenticate(user=context.admin)
    context.last_response = context.api.post(
        f"/api/fiscal/receipts/{context.receipt.id}/retry/", {}, format="json"
    )
    assert context.last_response.status_code == 200, context.last_response.content


@then("retry created a new pending fiscal_print command")
def step_retry_new_command(context):
    cnt = DeviceCommand.objects.filter(
        clinic=context.clinic,
        command_type="fiscal_print",
        payload__receipt_pk=context.receipt.id,
    ).count()
    assert cnt >= 2
    pending = DeviceCommand.objects.filter(
        clinic=context.clinic,
        command_type="fiscal_print",
        payload__receipt_pk=context.receipt.id,
        status=DeviceCommand.CommandStatus.PENDING,
    ).count()
    assert pending >= 1


@then("receipt idempotency key stays the same")
def step_idempotency_same(context):
    context.receipt.refresh_from_db()
    assert str(context.receipt.idempotency_key) == context.initial_idempotency_key
