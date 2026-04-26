"""
This is where you would find the API endppoints necessady to drive the Teams and Creator Dashboard management.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from shows.models import Show

from ..models import Team, TeamMembership
from .serializers import (
    TeamDetailSerializer,
    TeamListSerializer,
    TeamMemberSerializer,
    TeamShowListSerializer,
)


class UserTeamListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    """
    Returns team information for all the teams the user is a member of.

    The response is a list of team objects, each with the following response format:
    {
      id: <uuid>,  # Team ID',
      name: 'Personal Channel',
      avatar: 'https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=100&h=100&fit=crop&crop=face',  # Team Avatar
      role: 'owner',
      memberCount: 3,
      verified: true,
    },
    """

    def get(self, request):
        teams = Team.objects.filter(members=request.user).only(
            "id", "uuid", "slug", "name", "avatar", "verified"
        )
        return Response(
            TeamListSerializer(teams, many=True, context={"request": request}).data
        )


# TODO: Get Team View to get team information for the user
class TeamDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    # TODO: could return a different response when not authenticated (or a team member) and return basic "public" details.

    def get(self, request, team_id):
        team = get_object_or_404(Team, uuid=team_id)
        return Response(TeamDetailSerializer(team))


class TeamMemberListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, team_id):
        memberships = (
            TeamMembership.objects.filter(
                team__uuid=team_id,
                team__members=request.user,
            )
            .select_related("user")
            .order_by("created_at")
        )
        return Response(
            TeamMemberSerializer(
                memberships, many=True, context={"request": request}
            ).data
        )


class TeamShowListAPIView(APIView):
    """
    GET /<team_uuid>/shows

    Returns the list of shows belonging to the specified team.
    The authenticated user must be a member of that team.

    Query params:
      team_id (required) — UUID of the team whose shows to return
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, team_id):
        if not team_id:
            return Response(
                {"detail": "team_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shows = (
            Show.objects.filter(
                team__uuid=team_id,
                team__members=request.user,
            )
            .select_related("team")
            .order_by("-updated_at")
        )

        serializer = TeamShowListSerializer(shows, many=True)
        return Response(serializer.data)
