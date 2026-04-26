from django.urls import path

from . import views

urlpatterns = [
    # Shows
    path("shows", views.ShowListView.as_view(), name="shows_list"),
    path(
        "chapter/playback-event",
        views.chapter_playback_event,
        name="chapter_playback_event",
    ),
    path("shows/genres", views.shows_genres, name="shows_genres"),
    path("shows/discover", views.shows_discover, name="shows_discover"),
    path("shows/trending", views.shows_trending, name="shows_trending"),
    # path("shows/category", views.shows_by_category, name="shows_by_category"),
    path("shows/search", views.shows_search, name="shows_search"),
    # path("shows/<str:category>", views.shows_category, name="shows_category"),
    path(
        "shows/<str:category>", views.ShowsCategoryView.as_view(), name="shows_category"
    ),
    # path("show/<str:show_id>", views.show_detail, name="show_detail"),
    path("show/<str:show_id>", views.ShowDetailView.as_view(), name="show_detail"),
    # Franchises
    # path("franchises", views.franchises_list, name="franchises_list"),
    # path(
    #     "franchises/<str:franchise_id>", views.franchise_detail, name="franchise_detail"
    # ),
    # path(
    #     "franchises/<str:franchise_id>/series",
    #     views.franchise_series,
    #     name="franchise_series",
    # ),
    # Series
    # path("series", views.series_list, name="series_list"),
    # path("series/<str:series_id>", views.series_detail, name="series_detail"),
    # path(
    #     "series/<str:series_id>/episodes", views.series_episodes, name="series_episodes"
    # ),
    # Episodes
    path("episodes", views.episodes_list, name="episodes_list"),
    path(
        "episode/<str:episode_id>",
        views.EpisodeDetailView.as_view(),
        name="episode_detail",
    ),
    # Watchlist
    path("watchlist", views.watchlist_get, name="watchlist_get"),
    path("watchlist/add", views.watchlist_add, name="watchlist_add"),
    path("watchlist/remove", views.watchlist_remove, name="watchlist_remove"),
    path(
        "watchlist/check/<str:show_id>", views.watchlist_check, name="watchlist_check"
    ),
    # Playback # TODO: move somewhere else
    # path(
    #     "playback/next", views.playback_next, name="playback_next"
    # ),  # not sure if this is going to be used anymore
    # Episode with Playlist
    path(
        "episode/<str:episode_id>",
        views.EpisodeDetailView.as_view(),
        name="episode_detail",
    ),
    # Video playback info
    path(
        "video/<str:video_id>/playback", views.VideoURLView.as_view(), name="video_url"
    ),
    # Issues CloudFront signed cookies scoped to videos/{uuid}/hls/* then
    # redirects the client to the master manifest on CloudFront.
    path(
        "video/<str:video_id>/hls/",
        views.SignedPlaylistView.as_view(),
        name="hls_playlist",
    ),
    # get the video URL for playback.
    # A 200 response will include a time-limited URL to the video file,
    # a 402 response indicates the user needs to purchase access to view the video.
    # a 404 will indicate the video does not exist.
    # A 401 will tell the user they need to login.
    path(
        "video/<str:video_id>/purchase",
        views.VideoPurchaseView.as_view(),
        name="video_purchase",
    ),
    # Video details
    path("video/<str:video_id>", views.VideoDetailView.as_view(), name="video_detail"),
    # Video rating (like / dislike)
    path("video/<str:video_id>/rate", views.video_rate, name="video_rate"),
]
