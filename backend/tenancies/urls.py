from django.urls import path

from tenancies.views import (
    AssignmentCancelView,
    AssignmentCheckInView,
    AssignmentCheckOutView,
    AssignmentDetailView,
    AssignmentListCreateView,
    AssignmentTransferView,
    AvailabilityView,
    TenancyCancelView,
    TenancyDetailView,
    TenancyEndView,
    TenancyListCreateView,
)

urlpatterns = [
    path("tenancies/", TenancyListCreateView.as_view(), name="tenancy-list"),
    path(
        "tenancies/<str:tenancy_id>/",
        TenancyDetailView.as_view(),
        name="tenancy-detail",
    ),
    path(
        "tenancies/<str:tenancy_id>/end/",
        TenancyEndView.as_view(),
        name="tenancy-end",
    ),
    path(
        "tenancies/<str:tenancy_id>/cancel/",
        TenancyCancelView.as_view(),
        name="tenancy-cancel",
    ),
    path("assignments/", AssignmentListCreateView.as_view(), name="assignment-list"),
    path(
        "assignments/<str:assignment_id>/",
        AssignmentDetailView.as_view(),
        name="assignment-detail",
    ),
    path(
        "assignments/<str:assignment_id>/check-in/",
        AssignmentCheckInView.as_view(),
        name="assignment-check-in",
    ),
    path(
        "assignments/<str:assignment_id>/check-out/",
        AssignmentCheckOutView.as_view(),
        name="assignment-check-out",
    ),
    path(
        "assignments/<str:assignment_id>/cancel/",
        AssignmentCancelView.as_view(),
        name="assignment-cancel",
    ),
    path(
        "assignments/<str:assignment_id>/transfer/",
        AssignmentTransferView.as_view(),
        name="assignment-transfer",
    ),
    path("availability/", AvailabilityView.as_view(), name="availability"),
]
