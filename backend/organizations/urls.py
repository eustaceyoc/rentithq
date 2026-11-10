from django.urls import path

from organizations.views import (
    MembershipDetailView,
    MembershipListCreateView,
    PlanUsageView,
    WorkspaceDetailView,
    WorkspaceListCreateView,
)

urlpatterns = [
    path("workspaces/", WorkspaceListCreateView.as_view(), name="workspace-list"),
    path(
        "workspaces/<str:workspace_id>/",
        WorkspaceDetailView.as_view(),
        name="workspace-detail",
    ),
    path("memberships/", MembershipListCreateView.as_view(), name="membership-list"),
    path(
        "memberships/<str:membership_id>/",
        MembershipDetailView.as_view(),
        name="membership-detail",
    ),
    path("plan/", PlanUsageView.as_view(), name="plan-usage"),
]
