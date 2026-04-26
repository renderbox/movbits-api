from django.urls import path

from . import views

urlpatterns = [
    path("analytics/kpis", views.kpis, name="analytics_kpis"),
    path("analytics/overview", views.analytics_overview, name="analytics_overview"),
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
    path(
        "analytics/<str:content_id>/range",
        views.analytics_range,
        name="analytics_range",
    ),
    path(
        "analytics/<str:content_id>/popularity",
        views.analytics_popularity,
        name="analytics_popularity",
    ),
    path(
        "analytics/<str:content_id>/geography",
        views.analytics_geography,
        name="analytics_geography",
    ),
    path(
        "analytics/<str:content_id>/devices",
        views.analytics_devices,
        name="analytics_devices",
    ),
    path(
        "analytics/<str:content_id>/retention",
        views.analytics_retention,
        name="analytics_retention",
    ),
    path(
        "analytics/<str:content_id>/revenue",
        views.analytics_revenue,
        name="analytics_revenue",
    ),
    path(
        "analytics/<str:content_id>/engagement",
        views.analytics_engagement,
        name="analytics_engagement",
    ),
    path(
        "analytics/top-performing",
        views.analytics_top_performing,
        name="analytics_top_performing",
    ),
    path("analytics/compare", views.analytics_compare, name="analytics_compare"),
    path(
        "analytics/<str:content_id>/export",
        views.analytics_export,
        name="analytics_export",
    ),
    path(
        "analytics/<str:content_id>/realtime",
        views.analytics_realtime,
        name="analytics_realtime",
    ),
    path(
        "analytics/views-over-time",
        views.views_over_time,
        name="analytics_views-over-timne",
    ),
    path(
        "analytics/revenue-over-time",
        views.revenue_over_time,
        name="analytics_revenue-over-time",
    ),
]
