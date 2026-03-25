from contextvars import ContextVar

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_user_id_var: ContextVar[str] = ContextVar("user_id", default="-")
_clinic_id_var: ContextVar[str] = ContextVar("clinic_id", default="-")


def set_request_context(request_id: str, user_id: str, clinic_id: str) -> None:
    _request_id_var.set(request_id)
    _user_id_var.set(user_id)
    _clinic_id_var.set(clinic_id)


def clear_request_context() -> None:
    _request_id_var.set("-")
    _user_id_var.set("-")
    _clinic_id_var.set("-")


def get_request_context() -> tuple[str, str, str]:
    return (
        _request_id_var.get(),
        _user_id_var.get(),
        _clinic_id_var.get(),
    )
