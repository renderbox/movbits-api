from django.urls import path

from . import views

urlpatterns = [
    path(  # TODO: need to correct the inconsistency of this URL pattern
        "shows/<str:show_id>/analytics", views.content_analytics, name="show_analytics"
    ),
    path(  # TODO: need to correct the inconsistency of this URL pattern
        "franchises/<str:franchise_id>/analytics",
        views.content_analytics,
        name="franchise_analytics",
    ),
    path(  # TODO: need to correct the inconsistency of this URL pattern
        "series/<str:series_id>/analytics",
        views.content_analytics,
        name="series_analytics",
    ),
    path(  # TODO: need to correct the inconsistency of this URL pattern
        "episodes/<str:episode_id>/analytics",
        views.content_analytics,
        name="episode_analytics",
    ),
]
