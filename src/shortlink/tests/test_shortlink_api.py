from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from shortlink.models import ReferralClick, ReferralLink
from shows.models import Show
from team.models import Team

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_show(title="Test Show", team=None):
    site, _ = Site.objects.get_or_create(
        id=1, defaults={"domain": "example.com", "name": "example"}
    )
    if team is None:
        team, _ = Team.objects.get_or_create(name="Default Team", slug="default-team")
    return Show.objects.create(title=title, team=team, site=site)


def make_user(username="testuser", password="password"):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password=password
    )


# ---------------------------------------------------------------------------
# List / Create  GET|POST /shortlink/?show=<slug|uuid>
# ---------------------------------------------------------------------------


class ReferralLinkListCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        self.team = Team.objects.create(name="Creator Team", slug="creator-team")
        self.show = make_show(team=self.team)
        self.list_create_url = reverse("shortlink_api:referral_links")

    def _auth(self):
        self.client.force_authenticate(self.user)

    # --- GET ---

    def test_list_requires_auth(self):
        url = f"{self.list_create_url}?show={self.show.slug}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_returns_empty_for_new_show(self):
        self._auth()
        url = f"{self.list_create_url}?show={self.show.slug}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_list_returns_active_links_by_slug(self):
        self._auth()
        ReferralLink.objects.create(show=self.show, name="Active Link")
        deleted = ReferralLink.objects.create(
            show=self.show, name="Deleted Link", slug="deleted-link"
        )
        deleted.delete()

        url = f"{self.list_create_url}?show={self.show.slug}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Active Link")

    def test_list_resolves_show_by_uuid(self):
        self._auth()
        ReferralLink.objects.create(show=self.show, name="UUID Link")
        url = f"{self.list_create_url}?show={self.show.uuid}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_missing_show_param_returns_400(self):
        self._auth()
        response = self.client.get(self.list_create_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_unknown_show_returns_404(self):
        self._auth()
        url = f"{self.list_create_url}?show=does-not-exist"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- POST ---

    def test_create_requires_auth(self):
        response = self.client.post(
            self.list_create_url,
            {"show": self.show.slug, "title": "Link"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_minimal_link(self):
        self._auth()
        payload = {
            "show": self.show.slug,
            "title": "Camera Gear",
            "description": "Get 10% off",
            "ctaText": "Shop Now",
            "linkType": "shared",
            "enabled": True,
            "email": "",
        }
        response = self.client.post(self.list_create_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Camera Gear")
        self.assertIn("/r/", response.data["url"])
        self.assertEqual(response.data["clicks"], 0)
        self.assertTrue(ReferralLink.objects.filter(name="Camera Gear").exists())

    def test_create_with_all_fields(self):
        self._auth()
        payload = {
            "show": self.show.slug,
            "title": "Full Link",
            "description": "Desc",
            "ctaText": "Buy Now",
            "linkType": "unique",
            "validFrom": "2026-01-01",
            "validTo": "2026-12-31",
            "enabled": False,
            "email": "user@example.com",
        }
        response = self.client.post(self.list_create_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        link = ReferralLink.objects.get(name="Full Link")
        self.assertEqual(link.link_type, "unique")
        self.assertFalse(link.enabled)
        self.assertEqual(link.assigned_email, "user@example.com")

    def test_create_missing_show_returns_400(self):
        self._auth()
        response = self.client.post(
            self.list_create_url, {"title": "Orphan"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_unknown_show_returns_404(self):
        self._auth()
        payload = {
            "show": "ghost-show",
            "title": "Link",
            "linkType": "shared",
            "enabled": True,
        }
        response = self.client.post(self.list_create_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_url_contains_slug(self):
        self._auth()
        payload = {
            "show": self.show.slug,
            "title": "Slug URL Test",
            "ctaText": "Go",
            "linkType": "shared",
            "enabled": True,
            "email": "",
            "description": "",
        }
        response = self.client.post(self.list_create_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        link = ReferralLink.objects.get(name="Slug URL Test")
        self.assertIn(link.slug, response.data["url"])

    def test_serializer_shape(self):
        self._auth()
        ReferralLink.objects.create(
            show=self.show, name="Shape Test", link_type="unique"
        )
        url = f"{self.list_create_url}?show={self.show.slug}"
        response = self.client.get(url)
        item = response.data[0]
        for field in [
            "id",
            "title",
            "url",
            "description",
            "ctaText",
            "linkType",
            "clicks",
            "enabled",
        ]:
            self.assertIn(field, item)


# ---------------------------------------------------------------------------
# Update / Delete  PATCH|DELETE /shortlink/<slug>/
# ---------------------------------------------------------------------------


class ReferralLinkDetailTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user("detailuser")
        self.team = Team.objects.create(name="Detail Team", slug="detail-team")
        self.show = make_show(team=self.team)
        self.link = ReferralLink.objects.create(
            show=self.show,
            name="Original Name",
            link_type="shared",
            enabled=True,
        )

    def _url(self, slug=None):
        return reverse(
            "shortlink_api:referral_link_detail",
            kwargs={"slug": slug or self.link.slug},
        )

    def _auth(self):
        self.client.force_authenticate(self.user)

    # --- PATCH ---

    def test_update_requires_auth(self):
        response = self.client.patch(self._url(), {"title": "New"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_title(self):
        self._auth()
        response = self.client.patch(
            self._url(), {"title": "Updated Name"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Name")
        self.link.refresh_from_db()
        self.assertEqual(self.link.name, "Updated Name")

    def test_update_enabled_flag(self):
        self._auth()
        self.client.patch(self._url(), {"enabled": False}, format="json")
        self.link.refresh_from_db()
        self.assertFalse(self.link.enabled)

    def test_update_link_type(self):
        self._auth()
        self.client.patch(self._url(), {"linkType": "unique"}, format="json")
        self.link.refresh_from_db()
        self.assertEqual(self.link.link_type, "unique")

    def test_update_missing_slug_returns_404(self):
        self._auth()
        response = self.client.patch(
            self._url("no-such-slug"), {"title": "X"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_deleted_link_returns_404(self):
        self._auth()
        self.link.delete()
        response = self.client.patch(self._url(), {"title": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- DELETE ---

    def test_delete_requires_auth(self):
        response = self.client.delete(self._url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_soft_deletes(self):
        self._auth()
        response = self.client.delete(self._url())
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.link.refresh_from_db()
        self.assertTrue(self.link.deleted)

    def test_delete_hides_from_list(self):
        self._auth()
        self.client.delete(self._url())
        list_url = f"{reverse('shortlink_api:referral_links')}?show={self.show.slug}"
        response = self.client.get(list_url)
        self.assertEqual(response.data, [])

    def test_delete_already_deleted_returns_404(self):
        self._auth()
        self.link.delete()
        response = self.client.delete(self._url())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Batch generate  POST /shortlink/batch/
# ---------------------------------------------------------------------------


class BatchGenerateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user("batchuser")
        self.team = Team.objects.create(name="Batch Team", slug="batch-team")
        self.show = make_show(team=self.team)
        self.url = reverse("shortlink_api:batch_generate")

    def _auth(self):
        self.client.force_authenticate(self.user)

    def test_batch_requires_auth(self):
        response = self.client.post(
            self.url,
            {"show": self.show.slug, "title": "T", "mode": "count", "count": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_batch_count_mode_creates_correct_number(self):
        self._auth()
        payload = {
            "show": self.show.slug,
            "title": "Campaign",
            "mode": "count",
            "count": 5,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["count"], 5)
        self.assertEqual(len(response.data["generated"]), 5)
        self.assertEqual(ReferralLink.objects.filter(show=self.show).count(), 5)

    def test_batch_count_mode_links_are_unique(self):
        self._auth()
        payload = {
            "show": self.show.slug,
            "title": "Unique",
            "mode": "count",
            "count": 10,
        }
        response = self.client.post(self.url, payload, format="json")
        urls = [item["url"] for item in response.data["generated"]]
        self.assertEqual(len(urls), len(set(urls)))

    def test_batch_email_mode_assigns_emails(self):
        self._auth()
        emails = "alice@example.com\nbob@example.com\ncarol@example.com"
        payload = {
            "show": self.show.slug,
            "title": "Influencers",
            "mode": "emails",
            "emails": emails,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["count"], 3)
        assigned = {item["email"] for item in response.data["generated"]}
        self.assertEqual(
            assigned, {"alice@example.com", "bob@example.com", "carol@example.com"}
        )

    def test_batch_email_mode_persists_emails_to_db(self):
        self._auth()
        emails = "x@example.com\ny@example.com"
        payload = {
            "show": self.show.slug,
            "title": "Email Batch",
            "mode": "emails",
            "emails": emails,
        }
        self.client.post(self.url, payload, format="json")
        db_emails = set(
            ReferralLink.objects.filter(show=self.show).values_list(
                "assigned_email", flat=True
            )
        )
        self.assertIn("x@example.com", db_emails)
        self.assertIn("y@example.com", db_emails)

    def test_batch_missing_show_returns_400(self):
        self._auth()
        response = self.client.post(
            self.url, {"title": "T", "mode": "count", "count": 1}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_unknown_show_returns_404(self):
        self._auth()
        payload = {"show": "ghost", "title": "T", "mode": "count", "count": 1}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_batch_links_are_unique_type(self):
        self._auth()
        payload = {
            "show": self.show.slug,
            "title": "Batch",
            "mode": "count",
            "count": 3,
        }
        self.client.post(self.url, payload, format="json")
        types = set(
            ReferralLink.objects.filter(show=self.show).values_list(
                "link_type", flat=True
            )
        )
        self.assertEqual(types, {"unique"})

    def test_batch_invalid_count_returns_400(self):
        self._auth()
        payload = {
            "show": self.show.slug,
            "title": "Bad",
            "mode": "count",
            "count": "notanumber",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_response_includes_url(self):
        self._auth()
        payload = {
            "show": self.show.slug,
            "title": "URL Check",
            "mode": "count",
            "count": 1,
        }
        response = self.client.post(self.url, payload, format="json")
        item = response.data["generated"][0]
        self.assertIn("code", item)
        self.assertIn("url", item)
        self.assertIn("/r/", item["url"])


# ---------------------------------------------------------------------------
# Viewer-facing lookup  GET /shortlink/referral/<slug>/
# ---------------------------------------------------------------------------


class ReferralLookupTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user("lookupuser")
        self.team = Team.objects.create(name="Lookup Team", slug="lookup-team")
        self.show = make_show(team=self.team)
        self.link = ReferralLink.objects.create(show=self.show, name="Lookup Link")

    def _url(self, slug=None):
        return reverse(
            "shortlink_api:referral_lookup", kwargs={"slug": slug or self.link.slug}
        )

    # ── access ──────────────────────────────────────────────────────────────────

    def test_lookup_is_public(self):
        # Referral lookup must be accessible without authentication so that
        # anonymous visitors can click referral links before signing up.
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_lookup_returns_show_slug(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], self.link.slug)
        self.assertEqual(response.data["showSlug"], self.show.slug)

    def test_lookup_missing_slug_returns_404(self):
        response = self.client.get(self._url("no-such-slug"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_lookup_deleted_link_returns_404(self):
        self.link.delete()
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ── click_count (legacy) ─────────────────────────────────────────────────

    def test_lookup_increments_click_count(self):
        self.assertEqual(self.link.click_count, 0)
        self.client.get(self._url())
        self.link.refresh_from_db()
        self.assertEqual(self.link.click_count, 1)

    def test_lookup_increments_on_each_hit(self):
        for _ in range(3):
            self.client.get(self._url())
        self.link.refresh_from_db()
        self.assertEqual(self.link.click_count, 3)

    # ── ReferralClick model ──────────────────────────────────────────────────

    def test_lookup_creates_referral_click(self):
        self.client.get(self._url())
        self.assertEqual(
            ReferralClick.objects.filter(referral_link=self.link).count(), 1
        )

    def test_lookup_creates_one_click_per_request(self):
        for _ in range(3):
            self.client.get(self._url())
        self.assertEqual(
            ReferralClick.objects.filter(referral_link=self.link).count(), 3
        )

    def test_lookup_click_has_anonymous_id(self):
        self.client.get(self._url())
        click = ReferralClick.objects.get(referral_link=self.link)
        self.assertIsNotNone(click.anonymous_id)

    def test_lookup_authenticated_click_has_no_attributed_user(self):
        # The click is created immediately; user attribution happens later via signal.
        self.client.force_authenticate(self.user)
        self.client.get(self._url())
        click = ReferralClick.objects.get(referral_link=self.link)
        self.assertIsNone(click.user)

    # ── anonymous-id cookie ──────────────────────────────────────────────────

    def test_lookup_sets_anon_cookie(self):
        response = self.client.get(self._url())
        self.assertIn(ReferralClick.ANON_COOKIE, response.cookies)

    def test_lookup_reuses_existing_anon_cookie(self):
        # First request generates the cookie value.
        first = self.client.get(self._url())
        anon_val = first.cookies[ReferralClick.ANON_COOKIE].value

        # Second request (cookie echoed back by APIClient) reuses the same UUID.
        self.client.cookies[ReferralClick.ANON_COOKIE] = anon_val
        self.client.get(self._url())

        clicks = ReferralClick.objects.filter(referral_link=self.link)
        self.assertEqual(clicks.count(), 2)
        # Both clicks share the same anonymous_id.
        ids = set(str(c.anonymous_id) for c in clicks)
        self.assertEqual(len(ids), 1)

    def test_lookup_cookie_has_correct_max_age(self):
        response = self.client.get(self._url())
        cookie = response.cookies[ReferralClick.ANON_COOKIE]
        self.assertEqual(int(cookie["max-age"]), ReferralClick.ANON_COOKIE_MAX_AGE)

    # ── session ──────────────────────────────────────────────────────────────

    def test_lookup_stores_click_id_in_session(self):
        # Replaces old test that checked the now-removed 'referral_id' key.
        self.client.get(self._url())
        click = ReferralClick.objects.get(referral_link=self.link)
        session = self.client.session
        self.assertEqual(session.get("referral_click_id"), click.pk)

    def test_lookup_stores_show_id_in_session(self):
        self.client.get(self._url())
        session = self.client.session
        self.assertEqual(session.get("referral_show_id"), self.show.pk)

    # ── BigQuery event emission ──────────────────────────────────────────────

    def test_lookup_emits_referral_clicked_event(self):
        mock_pub = MagicMock()
        with patch("events.emit.get_publisher", return_value=mock_pub):
            self.client.get(self._url())
        mock_pub.publish.assert_called_once()
        _, payload = mock_pub.publish.call_args[0]
        self.assertEqual(payload["event_type"], "referral.clicked")
        self.assertEqual(payload["referral_slug"], self.link.slug)
        self.assertEqual(payload["show_id"], str(self.show.uuid))

    def test_lookup_event_has_no_user_id_when_anonymous(self):
        mock_pub = MagicMock()
        with patch("events.emit.get_publisher", return_value=mock_pub):
            self.client.get(self._url())
        _, payload = mock_pub.publish.call_args[0]
        self.assertIsNone(payload["user_id"])

    def test_lookup_event_includes_user_id_when_authenticated(self):
        self.client.force_authenticate(self.user)
        mock_pub = MagicMock()
        with patch("events.emit.get_publisher", return_value=mock_pub):
            self.client.get(self._url())
        _, payload = mock_pub.publish.call_args[0]
        self.assertEqual(payload["user_id"], str(self.user.pk))
