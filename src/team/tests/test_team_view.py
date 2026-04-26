# from django.contrib.auth import get_user_model
# from django.test import TestCase
# from django.urls import reverse

# from team.models import Team


# class TeamViewTests(TestCase):
#     def setUp(self):
#         User = get_user_model()
#         self.user = User.objects.create_user(
#             email="member@example.com", username="testuser", password="password"
#         )
#         self.non_member = User.objects.create_user(
#             email="nonmember@example.com", username="nonmember", password="password"
#         )
#         self.team = Team.objects.create(name="Test Team")
#         self.team.members.add(self.user)

#     def test_dashboard_view_member_access(self):
#         self.client.login(username="member@example.com", password="password")
#         response = self.client.get(
#             reverse("team-overview", kwargs={"team_slug": self.team.slug})
#         )
#         self.assertEqual(response.status_code, 200)
#         self.assertContains(response, "Test Team")

#     def test_dashboard_view_non_member_redirect(self):
#         self.client.login(username="nonmember@example.com", password="password")
#         response = self.client.get(
#             reverse("team-overview", kwargs={"team_slug": self.team.slug})
#         )
#         self.assertEqual(response.status_code, 302)
#         self.assertRedirects(
#             response, reverse("team-catalog", kwargs={"team": self.team.slug})
#         )

#     def test_members_view_member_access(self):
#         self.client.login(username="member@example.com", password="password")
#         response = self.client.get(
#             reverse("team-members", kwargs={"team_slug": self.team.slug})
#         )
#         self.assertEqual(response.status_code, 200)
#         self.assertContains(response, "Members")

#     def test_members_view_non_member_redirect(self):
#         self.client.login(username="nonmember@example.com", password="password")
#         response = self.client.get(
#             reverse("team-members", kwargs={"team_slug": self.team.slug})
#         )
#         self.assertEqual(response.status_code, 302)
#         self.assertRedirects(
#             response, reverse("team-catalog", kwargs={"team": self.team.slug})
#         )

#     def test_content_view_member_access(self):
#         self.client.login(username="member@example.com", password="password")
#         response = self.client.get(
#             reverse("team-content", kwargs={"team_slug": self.team.slug})
#         )
#         self.assertEqual(response.status_code, 200)
#         self.assertContains(response, "Content")

#     def test_content_view_non_member_redirect(self):
#         self.client.login(username="nonmember@example.com", password="password")
#         response = self.client.get(
#             reverse("team-content", kwargs={"team_slug": self.team.slug})
#         )
#         self.assertEqual(response.status_code, 302)
#         self.assertRedirects(
#             response,
#             reverse("team-catalog", kwargs={"team": self.team.slug}),
#         )
