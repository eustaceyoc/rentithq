from django.urls import path

from maintenance.views import (
    MaintenanceRequestDetailView,
    MaintenanceRequestListCreateView,
)

urlpatterns = [
    path(
        "maintenance-requests/",
        MaintenanceRequestListCreateView.as_view(),
        name="maintenance-list",
    ),
    path(
        "maintenance-requests/<str:request_id>/",
        MaintenanceRequestDetailView.as_view(),
        name="maintenance-detail",
    ),
]
