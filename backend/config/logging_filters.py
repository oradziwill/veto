import logging

from .request_context import get_request_context


class RequestContextFilter(logging.Filter):
    """
    Inject request-scoped context into all log records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        request_id, user_id, clinic_id = get_request_context()
        record.request_id = request_id
        record.user_id = user_id
        record.clinic_id = clinic_id
        return True
