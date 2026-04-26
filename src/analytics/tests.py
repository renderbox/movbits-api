import pytest
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.urls import reverse
from rest_framework.test import APIClient

from shows.models import Episode, Show
from team.models import Team, TeamMembership

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(email="analyst@example.com", username="analyst"):
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


def make_episode(show, title="Test Episode"):
    return Episode.objects.create(show=show, title=title)


# ---------------------------------------------------------------------------
# analytics_top_performing
# ---------------------------------------------------------------------------

URL = reverse("analytics_top_performing")


@pytest.mark.django_db
class TestTopPerforming:
    def setup_method(self):
        self.client = APIClient()
        self.user = make_user()
        self.team = make_team()
        make_membership(self.user, self.team)
        self.client.force_authenticate(user=self.user)

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(URL)
        assert response.status_code == 401

    def test_returns_episodes_for_team(self):
        show = make_show(self.team)
        make_episode(show, "Episode One")
        make_episode(show, "Episode Two")

        response = self.client.get(URL, {"teamId": str(self.team.uuid)})

        assert response.status_code == 200
        assert len(response.data) == 2
        titles = {item["title"] for item in response.data}
        assert titles == {"Episode One", "Episode Two"}

    def test_empty_for_team_with_no_episodes(self):
        response = self.client.get(URL, {"teamId": str(self.team.uuid)})

        assert response.status_code == 200
        assert response.data == []

    def test_respects_limit(self):
        show = make_show(self.team)
        for i in range(5):
            make_episode(show, f"Episode {i}")

        response = self.client.get(URL, {"teamId": str(self.team.uuid), "limit": 3})

        assert response.status_code == 200
        assert len(response.data) == 3

    def test_excludes_other_teams_episodes(self):
        other_team = make_team("Other Team")
        other_show = make_show(other_team, "Other Show")
        make_episode(other_show, "Other Episode")

        my_show = make_show(self.team)
        make_episode(my_show, "My Episode")

        response = self.client.get(URL, {"teamId": str(self.team.uuid)})

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["title"] == "My Episode"

    def test_without_team_id_returns_all_active_episodes(self):
        team_b = make_team("Team B")
        make_episode(make_show(self.team), "Ep A")
        make_episode(make_show(team_b, "Show B"), "Ep B")

        response = self.client.get(URL)

        assert response.status_code == 200
        assert len(response.data) == 2

    def test_response_shape(self):
        show = make_show(self.team)
        make_episode(show, "Shape Check Episode")

        response = self.client.get(URL, {"teamId": str(self.team.uuid)})

        assert response.status_code == 200
        item = response.data[0]
        for field in (
            "id",
            "title",
            "type",
            "views",
            "revenue",
            "engagement",
            "thumbnail",
        ):
            assert field in item, f"Missing field: {field}"

    def test_type_field_is_episode(self):
        make_episode(make_show(self.team), "Type Check")

        response = self.client.get(URL, {"teamId": str(self.team.uuid)})

        assert response.data[0]["type"] == "episode"

    def test_excludes_inactive_episodes(self):
        show = make_show(self.team)
        active_ep = make_episode(show, "Active Episode")
        Episode.objects.create(show=show, title="Inactive Episode", active=False)

        response = self.client.get(URL, {"teamId": str(self.team.uuid)})

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["id"] == str(active_ep.uuid)
