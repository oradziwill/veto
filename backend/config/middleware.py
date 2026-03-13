import uuid

from .request_context import clear_request_context, set_request_context


class RequestContextMiddleware:
    """
    Add request context (request_id/user_id/clinic_id) for structured logs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        request.request_id = request_id

        user = getattr(request, "user", None)
        user_id = str(getattr(user, "id", "-")) if getattr(user, "is_authenticated", False) else "-"
        clinic_id = (
            str(getattr(user, "clinic_id", "-"))
            if getattr(user, "is_authenticated", False)
            else "-"
        )

        set_request_context(request_id=request_id, user_id=user_id, clinic_id=clinic_id)
        try:
            response = self.get_response(request)
        finally:
            clear_request_context()

        response["X-Request-ID"] = request_id
        return response
