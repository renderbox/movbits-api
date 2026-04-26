# from django.test import TestCase
# from django.urls import reverse

# from team.models import Team


# class BaseCatalogViewsTests(TestCase):

#     def setUp(self):
#         self.team = Team.objects.create(name="Example Team", slug="example-team")

#     def test_catalog_view(self):
#         response = self.client.get(reverse("catalog"))
#         self.assertEqual(response.status_code, 200)

#     def test_trending_view(self):
#         response = self.client.get(reverse("trending"))
#         self.assertEqual(response.status_code, 200)

#     def test_team_catalog_view(self):
#         response = self.client.get(
#             reverse("team-catalog", kwargs={"team": "example-team"})
#         )
#         self.assertEqual(response.status_code, 200)

#     def test_must_see_view(self):
#         response = self.client.get(reverse("must-see"))
#         self.assertEqual(response.status_code, 200)

#     def test_hidden_gems_view(self):
#         response = self.client.get(reverse("hidden-gems"))
#         self.assertEqual(response.status_code, 200)
