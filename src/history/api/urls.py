from django.urls import path

from . import views

urlpatterns = [
    path("", views.viewing_history_list, name="viewing_history_list"),
    path("add", views.viewing_history_add, name="viewing_history_add"),
    path(
        "<str:history_id>/progress",
        views.viewing_history_update_progress,
        name="viewing_history_update_progress",
    ),
    path(
        "<str:history_id>",
        views.viewing_history_remove,
        name="viewing_history_remove",
    ),
    path(
        "clear",
        views.viewing_history_clear,
        name="viewing_history_clear",
    ),
    path(
        "continue-watching",
        views.viewing_history_continue_watching,
        name="viewing_history_continue_watching",
    ),
    path(
        "recent",
        views.viewing_history_recent,
        name="viewing_history_recent",
    ),
    path(
        "stats",
        views.viewing_history_stats,
        name="viewing_history_stats",
    ),
    path(
        "recommendations",
        views.viewing_history_recommendations,
        name="viewing_history_recommendations",
    ),
    path(
        "export",
        views.viewing_history_export,
        name="viewing_history_export",
    ),
    path(
        "check/<str:content_id>",
        views.viewing_history_check,
        name="viewing_history_check",
    ),
]
