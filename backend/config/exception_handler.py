from rest_framework import exceptions as drf_exceptions
from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    """
    Standardize DRF error responses while keeping `detail` for backward compatibility.
    """
    response = drf_exception_handler(exc, context)
    if response is None:
        return response

    status_code = response.status_code
    details = response.data

    if isinstance(exc, drf_exceptions.ValidationError):
        code = "validation_error"
        message = "Validation failed."
    elif isinstance(exc, drf_exceptions.NotAuthenticated):
        code = "not_authenticated"
        message = "Authentication credentials were not provided."
    elif isinstance(exc, drf_exceptions.AuthenticationFailed):
        code = "authentication_failed"
        message = "Authentication failed."
    elif isinstance(exc, drf_exceptions.PermissionDenied):
        code = "permission_denied"
        message = "You do not have permission to perform this action."
    elif isinstance(exc, drf_exceptions.NotFound):
        code = "not_found"
        message = "Resource not found."
    else:
        code = "api_error"
        message = "Request failed."

    if isinstance(details, dict) and "detail" in details:
        message = str(details["detail"])
    elif not isinstance(details, dict):
        message = str(details)

    payload = {
        "code": code,
        "message": message,
        "detail": message,
        "details": details,
        "status": status_code,
    }
    if isinstance(details, dict):
        payload = {**details, **payload}
    response.data = payload
    return response
