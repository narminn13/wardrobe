from django.urls import path

from .views import (
    garment_archive,
    garment_detail,
    garment_list,
    garment_toggle_availability,
    garment_upload,
)

app_name = "wardrobe"

urlpatterns = [
    path(
        "",
        garment_list,
        name="list"
    ),

    path(
        "upload/",
        garment_upload,
        name="upload"
    ),

    path(
        "<int:pk>/",
        garment_detail,
        name="detail"
    ),

    path(
        "<int:pk>/archive/",
        garment_archive,
        name="archive"
    ),

    path(
        "<int:pk>/availability/",
        garment_toggle_availability,
        name="toggle_availability"
    ),
]