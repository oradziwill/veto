from django.urls import path

from .views import ClinicFeatureFlagsView

urlpatterns = [
    path("clinic-features/", ClinicFeatureFlagsView.as_view(), name="clinic-features"),
]
