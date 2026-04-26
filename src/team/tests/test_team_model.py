from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase

from team.models import Team


class TeamModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="teamuser@example.com", username="testuser", password="password"
        )
        self.site, created = Site.objects.get_or_create(
            domain="foobar.com", name="FooBar Site"
        )

    def test_create_team(self):
        team = Team.objects.create(name="Test Team")
        team.members.add(self.user)
        team.sites.add(self.site)

        self.assertEqual(team.name, "Test Team")
        self.assertIn(self.user, team.members.all())
        self.assertIn(self.site, team.sites.all())

    def test_team_slug_generation(self):
        team = Team.objects.create(name="Test Team")
        self.assertEqual(team.slug, "test-team")
