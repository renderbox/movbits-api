# from datetime import date, timedelta

# from django.contrib.auth import get_user_model
# from django.test import Client, TestCase
# from django.urls import reverse

# from microdrama.models import Episode, Series
# from shortlink.models import ReferralLink
# from team.models import Team


# class ReferralLinkTests(TestCase):
#     def setUp(self):
#         self.client = Client()

#         User = get_user_model()
#         # Approx 30 years old to get past DOB check middleware.
#         thirty_years_ago = date.today() - timedelta(days=30 * 365)
#         self.user = User.objects.create_user(
#             email="shortlinkuser@example.com",
#             username="testuser",
#             password="password",
#             date_of_birth=thirty_years_ago,
#         )
#         self.client.login(username="shortlinkuser@example.com", password="password")

#         self.team = Team.objects.create(name="Test Team", slug="test-team")
#         self.series = Series.objects.create(
#             title="Test Series",
#             slug="test-series",
#             team=self.team,
#             description="Test Description",
#         )
#         self.episode = Episode.objects.create(
#             title="Test Episode",
#             slug="test-episode",
#             series=self.series,  # Associate with a valid series
#         )
#         self.referral = ReferralLink.objects.create(
#             team=self.team,
#             episode=self.episode,
#             name="Test Referral",
#         )

#     def test_referral_link_redirects_to_episode(self):
#         response = self.client.get(
#             reverse("shortlink:referral", args=[self.referral.slug]),
#             follow=True,  # Follow the redirect to the final destination
#         )
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, "microdrama/player.html")

#     def test_referral_link_sets_session_variables(self):
#         response = self.client.get(
#             reverse("shortlink:referral", args=[self.referral.slug])
#         )
#         self.assertEqual(response.status_code, 302)  # Ensure redirection occurs
#         self.assertRedirects(response, self.referral.episode.get_absolute_url())

#         session = self.client.session
#         self.assertEqual(session["referral_episode_id"], self.episode.id)
#         self.assertEqual(session["referral_id"], self.referral.id)

#     def test_inactive_referral_link_redirects_to_home(self):
#         self.referral.deleted = True
#         self.referral.save()
#         response = self.client.get(
#             reverse("shortlink:referral", args=[self.referral.slug])
#         )
#         self.assertRedirects(response, reverse("core:home"))
