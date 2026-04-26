# from django.urls import path

# from .views import (
#     AcceptInviteView,
#     TeamContentView,
#     TeamDashboardView,
#     TeamMembersView,
#     TeamShortLinkView,
# )

# urlpatterns = [
#     path("<slug:team_slug>/", TeamDashboardView.as_view(), name="team-overview"),
#     path("<slug:team_slug>/members/", TeamMembersView.as_view(), name="team-members"),
#     path(
#         "<slug:team_slug>/members/<str:action>",
#         TeamMembersView.as_view(),
#         name="team-members-action",
#     ),
#     path("<slug:team_slug>/content/", TeamContentView.as_view(), name="team-content"),
#     path("invite/<str:token>/", AcceptInviteView.as_view(), name="accept-invite"),
#     path(
#         "<slug:team_slug>/shortlinks/",
#         TeamShortLinkView.as_view(),
#         name="team-shortlinks",
#     ),
# ]
