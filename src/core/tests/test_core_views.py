# from django.contrib.auth import get_user_model
# from django.contrib.sites.models import Site
# from django.test import Client, TestCase
# from django.urls import reverse

# from microdrama.models import Series

# from team.models import Team

# class CoreViewsTests(TestCase):
#     def setUp(self):
#         self.client = Client()
#         User = get_user_model()
#         self.user = User.objects.create_user(
#             email="test@example.com", password="password", username="testuser"
#         )

#     def test_home_view(self):
#         response = self.client.get(reverse("core:home"))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "core/home.html")

#     def test_terms_view(self):
#         response = self.client.get(reverse("core:terms"))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "core/terms.html")

#     def test_privacy_view(self):
#         response = self.client.get(reverse("core:privacy"))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "core/privacy.html")

#     def test_profile_view_requires_login(self):
#         response = self.client.get(reverse("core:profile"))
#         self.assertEqual(response.status_code, 302)  # Redirect to login
#         self.client.login(username="test@example.com", password="password")
#         response = self.client.get(reverse("core:profile"))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "core/profile.html")

#     def test_profile_edit_view_requires_login(self):
#         response = self.client.get(reverse("core:profile_edit"))
#         self.assertEqual(response.status_code, 302)  # Redirect to login
#         self.client.login(username="test@example.com", password="password")
#         response = self.client.get(reverse("core:profile_edit"))
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "core/profile_edit.html")

#     def test_catalog_search(self):
#         # Create test team
#         team = Team.objects.create(name="Test Team", slug="test-team")

#         # Create test series with unique slugs and associate with current site
#         current_site = Site.objects.get_current()
#         series_1 = Series.objects.create(
#             title="Test Series 1", slug="test-series-1", team=team
#         )
#         series_2 = Series.objects.create(
#             title="Another Series", slug="another-series", team=team
#         )
#         series_1.sites.add(current_site)
#         series_2.sites.add(current_site)

#         # Perform search
#         response = self.client.get(reverse("catalog") + "?q=Test")

#         # Check response
#         self.assertEqual(response.status_code, 200)
#         self.assertContains(response, "Test Series 1")
#         self.assertNotContains(response, "Another Series")

#         # Verify Series creation
#         self.assertEqual(Series.objects.count(), 2)
#         self.assertTrue(Series.objects.filter(title="Test Series 1").exists())
#         self.assertTrue(Series.objects.filter(title="Another Series").exists())
