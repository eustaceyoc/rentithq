from django.urls import path

from properties.views import (
    BedDetailView,
    BedListCreateView,
    BuildingDetailView,
    BuildingListCreateView,
    FloorDetailView,
    FloorListCreateView,
    PropertyDetailView,
    PropertyListCreateView,
    SpaceDetailView,
    SpaceListCreateView,
)

urlpatterns = [
    path("properties/", PropertyListCreateView.as_view(), name="property-list"),
    path(
        "properties/<str:property_id>/",
        PropertyDetailView.as_view(),
        name="property-detail",
    ),
    path("buildings/", BuildingListCreateView.as_view(), name="building-list"),
    path(
        "buildings/<str:building_id>/",
        BuildingDetailView.as_view(),
        name="building-detail",
    ),
    path("floors/", FloorListCreateView.as_view(), name="floor-list"),
    path("floors/<str:floor_id>/", FloorDetailView.as_view(), name="floor-detail"),
    path("spaces/", SpaceListCreateView.as_view(), name="space-list"),
    path("spaces/<str:space_id>/", SpaceDetailView.as_view(), name="space-detail"),
    path("beds/", BedListCreateView.as_view(), name="bed-list"),
    path("beds/<str:bed_id>/", BedDetailView.as_view(), name="bed-detail"),
]
