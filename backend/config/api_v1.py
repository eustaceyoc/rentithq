from django.urls import include, path

from common.health import HealthView, ReadyView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("health/ready/", ReadyView.as_view(), name="health-ready"),
    path("", include("accounts.urls")),
    path("", include("organizations.urls")),
    path("", include("properties.urls")),
    path("", include("residents.urls")),
    path("", include("bookings.urls")),
    path("", include("tenancies.urls")),
    path("", include("billing.urls")),
    path("", include("maintenance.urls")),
    path("", include("reports.urls")),
]
