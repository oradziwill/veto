"""Shared Behave step definitions used by multiple features."""

from behave import then


@then("the response status is {status:d}")
def step_response_status(context, status):
    assert context.last_response is not None
    assert context.last_response.status_code == status, (
        f"expected {status}, got {context.last_response.status_code}: "
        f"{getattr(context.last_response, 'data', context.last_response.content)}"
    )
