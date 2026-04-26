from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core.models import StoryUser

from .models import SiteInvitation


def make_staff_user(username="staff", **kwargs):
    user = StoryUser.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="testpass",
        is_staff=True,
        **kwargs,
    )
    return user


def make_regular_user(username="user"):
    return StoryUser.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="testpass",
    )


class VerifyInviteTests(TestCase):
    """GET /invitations/verify/ — public endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("invite_verify")

    def test_missing_key_returns_400(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["valid"])

    def test_invalid_key_returns_valid_false(self):
        resp = self.client.get(self.url, {"key": "doesnotexist"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["valid"])

    def test_accepted_invite_returns_valid_false(self):
        from django.utils import timezone

        inv = SiteInvitation.objects.create(
            email="used@example.com", accepted=timezone.now()
        )
        resp = self.client.get(self.url, {"key": inv.key})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["valid"])

    def test_valid_unused_invite_returns_true_with_email(self):
        inv = SiteInvitation.objects.create(email="new@example.com", name="Alice")
        resp = self.client.get(self.url, {"key": inv.key})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["valid"])
        self.assertEqual(resp.data["email"], "new@example.com")
        self.assertEqual(resp.data["name"], "Alice")

    @patch.object(SiteInvitation, "key_expired", return_value=True)
    def test_expired_invite_returns_valid_false(self, _mock):
        from django.utils import timezone

        inv = SiteInvitation.objects.create(email="old@example.com")
        # Mark as sent so the view checks key_expired()
        SiteInvitation.objects.filter(pk=inv.pk).update(sent=timezone.now())
        inv.refresh_from_db()
        resp = self.client.get(self.url, {"key": inv.key})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["valid"])


class InvitationListTests(TestCase):
    """GET + POST /invitations/ — staff only."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("invitation_list")
        self.staff = make_staff_user()

    def test_unauthenticated_returns_403(self):
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, [401, 403])

    def test_non_staff_returns_403(self):
        user = make_regular_user()
        self.client.force_authenticate(user=user)
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, [401, 403])

    def test_staff_can_list_invitations(self):
        SiteInvitation.objects.create(email="a@example.com")
        SiteInvitation.objects.create(email="b@example.com")
        self.client.force_authenticate(user=self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    @patch.object(SiteInvitation, "send_invitation")
    def test_staff_can_create_invitation(self, mock_send):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.url, {"email": "new@example.com", "name": "Bob"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["email"], "new@example.com")
        mock_send.assert_called_once()

    @patch.object(SiteInvitation, "send_invitation")
    def test_duplicate_active_invite_returns_400(self, mock_send):
        SiteInvitation.objects.create(email="dup@example.com")
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.url, {"email": "dup@example.com"})
        self.assertEqual(resp.status_code, 400)


class BulkInviteTests(TestCase):
    """POST /invitations/bulk/ — staff only."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("invitation_bulk")
        self.staff = make_staff_user()

    def test_unauthenticated_returns_403(self):
        resp = self.client.post(self.url, {})
        self.assertIn(resp.status_code, [401, 403])

    @patch.object(SiteInvitation, "send_invitation")
    def test_creates_campaign_and_invitations(self, mock_send):
        self.client.force_authenticate(user=self.staff)
        payload = {
            "campaignTitle": "Beta Launch",
            "emails": ["u1@example.com", "u2@example.com"],
        }
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["campaign"]["title"], "Beta Launch")
        self.assertEqual(len(resp.data["created"]), 2)
        self.assertEqual(resp.data["skipped"], [])
        self.assertEqual(mock_send.call_count, 2)

    @patch.object(SiteInvitation, "send_invitation")
    def test_skips_duplicate_emails(self, mock_send):
        SiteInvitation.objects.create(email="existing@example.com")
        self.client.force_authenticate(user=self.staff)
        payload = {
            "campaignTitle": "Wave 2",
            "emails": ["existing@example.com", "fresh@example.com"],
        }
        resp = self.client.post(self.url, payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["created"]), 1)
        self.assertEqual(len(resp.data["skipped"]), 1)


class InvitationDetailTests(TestCase):
    """DELETE + POST /invitations/<key>/ — staff only."""

    def setUp(self):
        self.client = APIClient()
        self.staff = make_staff_user()
        self.inv = SiteInvitation.objects.create(email="target@example.com")
        self.url = reverse("invitation_detail", kwargs={"key": self.inv.key})

    def test_unauthenticated_returns_403(self):
        resp = self.client.delete(self.url)
        self.assertIn(resp.status_code, [401, 403])

    def test_delete_revokes_invitation(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(SiteInvitation.objects.filter(pk=self.inv.pk).exists())

    def test_delete_nonexistent_returns_404(self):
        self.client.force_authenticate(user=self.staff)
        url = reverse("invitation_detail", kwargs={"key": "badkey"})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 404)

    @patch.object(SiteInvitation, "send_invitation")
    def test_resend_resets_sent_and_calls_send(self, mock_send):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)
        mock_send.assert_called_once()

    @patch.object(SiteInvitation, "send_invitation")
    def test_resend_already_accepted_returns_400(self, mock_send):
        from django.utils import timezone

        self.inv.accepted = timezone.now()
        self.inv.save(update_fields=["accepted"])
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 400)
        mock_send.assert_not_called()
