"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from config.health import health, health_ready

urlpatterns = [
    path("health/", health),
    path("health/ready/", health_ready),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # JWT auth
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include("apps.scheduling.urls")),
    path("api/", include("apps.patients.urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.tenancy.urls")),
    path("api/", include("apps.clients.urls")),
    path("api/", include("apps.inventory.urls")),
    path("api/", include("apps.medical.urls")),
    path("api/", include("apps.drug_catalog.urls")),
    path("api/billing/", include("apps.billing.urls")),
    path("api/", include("apps.labs.urls")),
    path("api/", include("apps.reminders.urls")),
    path("api/", include("apps.notifications.urls")),
    path("api/", include("apps.documents.urls")),
    path("api/", include("apps.consents.urls")),
    path("api/", include("apps.audit.urls")),
    path("api/", include("apps.reports.urls")),
    path("api/", include("apps.webhooks.urls")),
    path("api/portal/", include("apps.portal.urls")),
    path("api/", include("apps.inbox.urls")),
]
