from django.urls import path

from reports.views import (
    ArrearsReportView,
    CollectionsReportView,
    MaintenanceReportView,
    OccupancyReportView,
)

urlpatterns = [
    path("reports/occupancy/", OccupancyReportView.as_view(), name="report-occupancy"),
    path("reports/arrears/", ArrearsReportView.as_view(), name="report-arrears"),
    path(
        "reports/collections/",
        CollectionsReportView.as_view(),
        name="report-collections",
    ),
    path(
        "reports/maintenance/",
        MaintenanceReportView.as_view(),
        name="report-maintenance",
    ),
]
