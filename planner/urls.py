from django.urls import path

from .views import create_plan, current_week, weekly_plan


app_name = "planner"


urlpatterns = [
    path(
        "create/",
        create_plan,
        name="create"
    ),

    path(
        "current/",
        current_week,
        name="current"
    ),

    path(
        "<int:pk>/",
        weekly_plan,
        name="weekly"
    ),
]