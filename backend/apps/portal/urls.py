from django.urls import path

from . import views

urlpatterns = [
    path("clinics/<slug:slug>/", views.PortalClinicPublicView.as_view()),
    path("clinics/<slug:slug>/vets/", views.PortalClinicVetsPublicView.as_view()),
    path("clinics/<slug:slug>/availability/", views.PortalClinicAvailabilityPublicView.as_view()),
    path("auth/request-code/", views.PortalAuthRequestCodeView.as_view()),
    path("auth/confirm-code/", views.PortalAuthConfirmCodeView.as_view()),
    path("me/patients/", views.PortalMePatientsView.as_view()),
    path("availability/", views.PortalAvailabilityView.as_view()),
    path("appointments/", views.PortalAppointmentListCreateView.as_view()),
    path("appointments/<int:pk>/cancel/", views.PortalAppointmentCancelView.as_view()),
]
