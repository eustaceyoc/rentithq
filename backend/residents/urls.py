from django.urls import path

from residents.views import ResidentDetailView, ResidentListCreateView

urlpatterns = [
    path("residents/", ResidentListCreateView.as_view(), name="resident-list"),
    path(
        "residents/<str:resident_id>/",
        ResidentDetailView.as_view(),
        name="resident-detail",
    ),
]
