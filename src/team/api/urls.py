from django.urls import path

from . import views

urlpatterns = [
    # Teams endpoints (examples; teams client maps to teams)
    path("", views.UserTeamListAPIView.as_view(), name="get_teams"),
    path("<str:team_id>/", views.TeamDetailAPIView.as_view(), name="get_team"),
    path(
        "<str:team_id>/members/",
        views.TeamMemberListAPIView.as_view(),
        name="get_team_members",
    ),
    path(
        "<str:team_id>/shows/",
        views.TeamShowListAPIView.as_view(),
        name="get_team_shows",
    ),
]
