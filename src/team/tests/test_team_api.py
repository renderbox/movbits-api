import pytest
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.urls import reverse
from rest_framework.test import APIClient

from shows.models import Show
from team.models import Team, TeamMembership

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(email="user@example.com", username="testuser"):
    return User.objects.create_user(email=email, username=username, password="password")


def make_team(name="Test Team"):
    return Team.objects.create(name=name)


def make_membership(user, team, role=TeamMembership.Role.OWNER):
    return TeamMembership.objects.create(user=user, team=team, role=role)


def make_show(team, title="Test Show"):
    site, _ = Site.objects.get_or_create(
        domain="example.com", defaults={"name": "Example"}
    )
    return Show.objects.create(team=team, site=site, title=title)


# ---------------------------------------------------------------------------
# GET /teams/ — UserTeamListAPIView
# ---------------------------------------------------------------------------

TEAMS_URL = reverse("get_teams")


@pytest.mark.django_db
class TestUserTeamList:
    def setup_method(self):
        self.client = APIClient()
        self.user = make_user()
        self.team = make_team()
        make_membership(self.user, self.team, role=TeamMembership.Role.OWNER)
        self.client.force_authenticate(user=self.user)

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(TEAMS_URL)
        assert response.status_code == 401

    def test_returns_teams_user_is_member_of(self):
        # other_team = make_team("Other Team")  # user is not a member

        response = self.client.get(TEAMS_URL)

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Test Team"

    def test_response_shape(self):
        response = self.client.get(TEAMS_URL)

        assert response.status_code == 200
        item = response.data[0]
        for field in (
            "id",
            "slug",
            "name",
            "avatar",
            "role",
            "memberCount",
            "verified",
        ):
            assert field in item, f"Missing field: {field}"

    def test_id_is_uuid_string(self):
        import uuid

        response = self.client.get(TEAMS_URL)

        assert response.status_code == 200
        team_id = response.data[0]["id"]
        # Should parse as a valid UUID without raising
        uuid.UUID(team_id)

    def test_slug_matches_team_slug(self):
        response = self.client.get(TEAMS_URL)

        assert response.status_code == 200
        assert response.data[0]["slug"] == self.team.slug

    def test_member_count_is_camel_case(self):
        """Regression: field was previously returned as member_count (snake_case)."""
        response = self.client.get(TEAMS_URL)

        assert response.status_code == 200
        item = response.data[0]
        assert "memberCount" in item
        assert "member_count" not in item

    def test_member_count_reflects_actual_count(self):
        extra_user = make_user(email="extra@example.com", username="extra")
        make_membership(extra_user, self.team, role=TeamMembership.Role.VIEWER)

        response = self.client.get(TEAMS_URL)

        assert response.status_code == 200
        assert response.data[0]["memberCount"] == 2

    def test_role_reflects_membership_role(self):
        response = self.client.get(TEAMS_URL)

        assert response.status_code == 200
        assert response.data[0]["role"] == "owner"

    def test_role_for_admin_membership(self):
        admin_user = make_user(email="admin@example.com", username="admin")
        admin_team = make_team("Admin Team")
        make_membership(admin_user, admin_team, role=TeamMembership.Role.ADMIN)
        self.client.force_authenticate(user=admin_user)

        response = self.client.get(TEAMS_URL)

        assert response.status_code == 200
        assert response.data[0]["role"] == "admin"

    def test_returns_multiple_teams(self):
        second_team = make_team("Second Team")
        make_membership(self.user, second_team, role=TeamMembership.Role.VIEWER)

        response = self.client.get(TEAMS_URL)

        assert response.status_code == 200
        assert len(response.data) == 2


# ---------------------------------------------------------------------------
# GET /teams/<uuid>/members/ — TeamMemberListAPIView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTeamMemberList:
    def setup_method(self):
        self.client = APIClient()
        self.user = make_user()
        self.team = make_team()
        make_membership(self.user, self.team, role=TeamMembership.Role.OWNER)
        self.client.force_authenticate(user=self.user)

    def _url(self, team_uuid=None):
        uuid = team_uuid or str(self.team.uuid)
        return reverse("get_team_members", kwargs={"team_id": uuid})

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(self._url())
        assert response.status_code == 401

    def test_returns_members_of_team(self):
        second_user = make_user(email="member2@example.com", username="member2")
        make_membership(second_user, self.team, role=TeamMembership.Role.EDITOR)

        response = self.client.get(self._url())

        assert response.status_code == 200
        assert len(response.data) == 2

    def test_response_shape(self):
        response = self.client.get(self._url())

        assert response.status_code == 200
        item = response.data[0]
        for field in ("id", "name", "email", "role", "joinedDate", "status"):
            assert field in item, f"Missing field: {field}"

    def test_non_member_sees_empty_list(self):
        """Non-members get an empty list (view filters by team__members=request.user)."""
        non_member = make_user(email="nonmember@example.com", username="nonmember")
        self.client.force_authenticate(user=non_member)

        response = self.client.get(self._url())

        assert response.status_code == 200
        assert response.data == []

    def test_role_is_human_readable(self):
        response = self.client.get(self._url())

        assert response.status_code == 200
        assert response.data[0]["role"] == "owner"

    def test_status_active_for_active_membership(self):
        response = self.client.get(self._url())

        assert response.status_code == 200
        assert response.data[0]["status"] == "active"

    def test_status_inactive_for_inactive_membership(self):
        inactive_user = make_user(email="inactive@example.com", username="inactive")
        TeamMembership.objects.create(
            user=inactive_user,
            team=self.team,
            role=TeamMembership.Role.VIEWER,
            active=False,
        )

        response = self.client.get(self._url())

        statuses = {item["status"] for item in response.data}
        assert "inactive" in statuses


# ---------------------------------------------------------------------------
# GET /teams/<uuid>/shows/ — TeamShowListAPIView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTeamShowList:
    def setup_method(self):
        self.client = APIClient()
        self.user = make_user()
        self.team = make_team()
        make_membership(self.user, self.team, role=TeamMembership.Role.OWNER)
        self.client.force_authenticate(user=self.user)

    def _url(self, team_uuid=None):
        uuid = team_uuid or str(self.team.uuid)
        return reverse("get_team_shows", kwargs={"team_id": uuid})

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(self._url())
        assert response.status_code == 401

    def test_returns_shows_for_team(self):
        make_show(self.team, "Show Alpha")
        make_show(self.team, "Show Beta")

        response = self.client.get(self._url())

        assert response.status_code == 200
        assert len(response.data) == 2

    def test_non_member_sees_empty_list(self):
        make_show(self.team, "Hidden Show")
        non_member = make_user(email="nobody@example.com", username="nobody")
        self.client.force_authenticate(user=non_member)

        response = self.client.get(self._url())

        assert response.status_code == 200
        assert response.data == []

    def test_response_shape(self):
        make_show(self.team)

        response = self.client.get(self._url())

        assert response.status_code == 200
        item = response.data[0]
        for field in (
            "id",
            "title",
            "type",
            "visibility",
            "views",
            "revenue",
            "lastUpdated",
            "thumbnail",
            "status",
        ):
            assert field in item, f"Missing field: {field}"

    def test_excludes_other_teams_shows(self):
        other_team = make_team("Other Team")
        make_show(other_team, "Other Show")
        make_show(self.team, "My Show")

        response = self.client.get(self._url())

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["title"] == "My Show"
