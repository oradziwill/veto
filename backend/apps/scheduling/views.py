"""
Scheduling API views.

Code lives in ``views_*.py``; this module re-exports classes for ``urls.py``
and stable import paths.
"""

from .views_appointments import AppointmentViewSet
from .views_hospital import HospitalStayViewSet
from .views_queue_availability import (
    AvailabilityRoomsView,
    AvailabilityView,
    RoomViewSet,
    WaitingQueueViewSet,
)
from .views_visit_recordings import (
    VisitRecordingDetailView,
    VisitRecordingListView,
    VisitRecordingUploadView,
    VisitTranscriptionJobDetailView,
    VisitTranscriptionView,
)

__all__ = [
    "AppointmentViewSet",
    "AvailabilityRoomsView",
    "AvailabilityView",
    "HospitalStayViewSet",
    "RoomViewSet",
    "VisitRecordingDetailView",
    "VisitRecordingListView",
    "VisitRecordingUploadView",
    "VisitTranscriptionJobDetailView",
    "VisitTranscriptionView",
    "WaitingQueueViewSet",
]
