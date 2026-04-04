from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppointmentViewSet,
    AvailabilityRoomsView,
    AvailabilityView,
    HospitalStayViewSet,
    RoomViewSet,
    VisitRecordingDetailView,
    VisitRecordingListView,
    VisitRecordingUploadView,
    VisitTranscriptionJobDetailView,
    VisitTranscriptionView,
    WaitingQueueViewSet,
)
from .views_assistant import (
    SchedulingCapacityInsightsView,
    SchedulingOptimizationSuggestionsView,
)
from .views_schedule import (
    ClinicHolidayViewSet,
    ClinicWorkingHoursViewSet,
    DutyAssignmentViewSet,
    GenerateScheduleView,
    VetAvailabilityExceptionViewSet,
    VetWorkingHoursViewSet,
)

router = DefaultRouter()
router.register(r"appointments", AppointmentViewSet, basename="appointments")
router.register(r"hospital-stays", HospitalStayViewSet, basename="hospital-stays")
router.register(r"rooms", RoomViewSet, basename="rooms")
router.register(r"queue", WaitingQueueViewSet, basename="queue")
router.register(r"schedule/working-hours", VetWorkingHoursViewSet, basename="working-hours")
router.register(r"schedule/exceptions", VetAvailabilityExceptionViewSet, basename="vet-exceptions")
router.register(r"schedule/holidays", ClinicHolidayViewSet, basename="clinic-holidays")
router.register(r"schedule/clinic-hours", ClinicWorkingHoursViewSet, basename="clinic-hours")
router.register(r"schedule/assignments", DutyAssignmentViewSet, basename="duty-assignments")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "visits/<int:appointment_id>/transcribe/",
        VisitTranscriptionView.as_view(),
        name="visit-transcribe",
    ),
    path(
        "visits/<int:appointment_id>/transcribe/jobs/<int:job_id>/",
        VisitTranscriptionJobDetailView.as_view(),
        name="visit-transcription-job",
    ),
    path(
        "visits/<int:appointment_id>/recordings/upload/",
        VisitRecordingUploadView.as_view(),
        name="visit-recording-upload",
    ),
    path(
        "visits/<int:appointment_id>/recordings/",
        VisitRecordingListView.as_view(),
        name="visit-recording-list",
    ),
    path(
        "visit-recordings/<int:recording_id>/",
        VisitRecordingDetailView.as_view(),
        name="visit-recording-detail",
    ),
    path("availability/", AvailabilityView.as_view(), name="availability"),
    path(
        "availability/rooms/",
        AvailabilityRoomsView.as_view(),
        name="availability-rooms",
    ),
    path("schedule/generate/", GenerateScheduleView.as_view(), name="schedule-generate"),
    path(
        "schedule/capacity-insights/",
        SchedulingCapacityInsightsView.as_view(),
        name="schedule-capacity-insights",
    ),
    path(
        "schedule/optimization-suggestions/",
        SchedulingOptimizationSuggestionsView.as_view(),
        name="schedule-optimization-suggestions",
    ),
]
