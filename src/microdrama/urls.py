from django.urls import path

from .views import (
    CatalogView,
    EnterDOBView,
    HiddenGemsView,
    MustSeeView,
    PlayerView,
    SeriesDetailView,
    TeamCatalogView,
    TrendingView,
    serve_signed_playlist,
)

urlpatterns = [
    path(
        "enter-dob/",
        EnterDOBView.as_view(),
        name="enter-dob",
    ),
    path(
        "hls/<uuid:uuid>/<str:filename>", serve_signed_playlist, name="signed_playlist"
    ),
    path(
        "trending/",
        TrendingView.as_view(),
        name="trending",
    ),
    path(
        "must-see/",
        MustSeeView.as_view(),
        name="must-see",
    ),
    path(
        "hidden-gems/",
        HiddenGemsView.as_view(),
        name="hidden-gems",
    ),
    path(
        "<slug:team>/<slug:series>/<slug:episode>/player/<int:chapter>/",
        PlayerView.as_view(),
        name="player-chapter",
    ),
    path(
        "<slug:team>/<slug:series>/<slug:episode>/player/",
        PlayerView.as_view(),
        name="player",
    ),
    path(
        "<slug:team>/<slug:series>/",
        SeriesDetailView.as_view(),
        name="series-detail",
    ),
    path(
        "<slug:team>/",
        TeamCatalogView.as_view(),
        name="team-catalog",
    ),
    path(
        "",
        CatalogView.as_view(),
        name="catalog",
    ),
]
