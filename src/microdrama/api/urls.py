from django.urls import path

from .views import (
    ChapterPlaybackAPIView,
    EpisodeWithPlaylistAPIView,
    HiddenGemsAPIView,
    MustSeeAPIView,
    SeriesCatalogAPIView,
    SeriesDetailAPIView,
    TrendingSeriesAPIView,
)

urlpatterns = [
    path(
        "video/<uuid:chapter_uuid>/",
        ChapterPlaybackAPIView.as_view(),
        name="chapter-video",
    ),
    path(
        "episode/<uuid:episode_uuid>/",
        EpisodeWithPlaylistAPIView.as_view(),
        name="episode",
    ),
    path("trending/", TrendingSeriesAPIView.as_view(), name="trending-videos"),
    path("must-see/", MustSeeAPIView.as_view(), name="must-see-videos"),
    path(
        "hidden-gems/",
        HiddenGemsAPIView.as_view(),
        name="hidden-gems-videos",
    ),
    path(
        "<slug:team_slug>/<slug:series_slug>/",
        SeriesDetailAPIView.as_view(),
        name="browse-videos",
    ),
    path(
        "",
        SeriesCatalogAPIView.as_view(),
        name="browse-videos",
    ),
]
