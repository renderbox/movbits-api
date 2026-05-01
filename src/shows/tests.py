import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from core.models import MBUser
from shows.api.serializers import ShowSerializer, VideoSerializer
from shows.models import Episode, RevShareDeal, Season, Show, Tag, Video, VideoReceipt
from team.models import Team
from wallet.models import CreditTypes, Wallet, WalletTransaction


class ShowSerializerTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Product Super Team", slug="product-super")
        self.site = Site.objects.get_current()
        self.show = Show.objects.create(
            team=self.team,
            site=self.site,
            title="Epic Adventure Time",
            description="A thrilling journey.",
            rating_value=48,
        )
        self.genre_tag = Tag.objects.create(
            name="Action", slug="action", tagtype=Tag.TagType.GENRE
        )
        self.show.tags.add(self.genre_tag)

        self.season = Season.objects.create(
            show=self.show, order=1, title="Season 1: The Journey Begins"
        )

        self.free_video = Video.objects.create(
            title="Departure Protocol", cdn=Video.CDNChoices.VIMEO, price=0
        )
        self.paid_video = Video.objects.create(
            title="Making Of", cdn=Video.CDNChoices.VIMEO, price=100
        )

        self.episode = Episode(
            id=1,
            show=self.show,
            season=self.season,
            order=1,
            title="Departure Protocol",
            description="Episode one description",
            rating_value=47,
            duration=3420,
        )
        self.episode.save()
        self.episode.playlist.add(self.free_video)
        Episode.objects.filter(pk=self.episode.pk).update(chapter_count=8)
        self.episode.refresh_from_db()

        self.extra_episode = Episode(
            id=2,
            show=self.show,
            order=2,
            title="Making Of Epic Adventure Time",
            description="Behind the scenes",
            rating_value=49,
            duration=3660,
        )
        self.extra_episode.save()
        self.extra_episode.playlist.add(self.paid_video)
        Episode.objects.filter(pk=self.extra_episode.pk).update(chapter_count=1)
        self.extra_episode.refresh_from_db()

    def test_show_serializer_matches_expected_structure(self):
        data = ShowSerializer(self.show).data

        self.assertEqual(data["id"], self.show.slug)
        self.assertEqual(data["title"], "Epic Adventure Time")
        self.assertEqual(data["longDescription"], self.show.description)
        self.assertEqual(data["rating"], 4.8)
        self.assertIn("Action", data["tags"])

        seasons = data["seasons"]
        self.assertEqual(len(seasons), 2)

        season_one = seasons[0]
        self.assertEqual(season_one["id"], self.season.slug)
        self.assertEqual(season_one["seasonNumber"], 1)
        self.assertEqual(len(season_one["episodes"]), 1)
        episode_data = season_one["episodes"][0]
        self.assertEqual(episode_data["id"], self.episode.slug)
        self.assertEqual(episode_data["chapterCount"], 8)
        self.assertFalse(episode_data["isLocked"])

        extras = seasons[1]
        self.assertEqual(extras["id"], "extras")
        self.assertEqual(extras["seasonNumber"], 9999)
        self.assertEqual(len(extras["episodes"]), 1)
        extra_episode_data = extras["episodes"][0]
        self.assertEqual(extra_episode_data["id"], self.extra_episode.slug)
        self.assertEqual(extra_episode_data["chapterCount"], 1)
        self.assertTrue(extra_episode_data["isLocked"])


class EpisodeDetailViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        team = Team.objects.create(name="Team Episode", slug="team-episode")
        self.site = Site.objects.get_current()
        show = Show.objects.create(
            team=team, site=self.site, title="Show", description="Desc"
        )
        season = Season.objects.create(show=show, order=1, title="S1")
        self.free_video = Video.objects.create(
            title="Chapter 1",
            cdn=Video.CDNChoices.VIMEO,
            price=0,
            duration=120,
            video_key="free-key",
        )
        self.paid_video = Video.objects.create(
            title="Chapter 2",
            cdn=Video.CDNChoices.S3_MEDIA_BUCKET,
            price=5,
            duration=180,
            video_key="paid-key",
        )
        self.episode = Episode.objects.create(
            show=show,
            season=season,
            order=1,
            title="Episode 1",
            description="Episode description",
        )
        self.episode.playlist.add(self.free_video, self.paid_video)

    def detail_url(self, episode_id):
        return reverse("episode_detail", kwargs={"episode_id": episode_id})

    def test_retrieves_episode_by_slug_with_playlist(self):
        response = self.client.get(self.detail_url(self.episode.slug))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.episode.slug)
        playlist = response.data.get("playlist", [])
        self.assertEqual(len(playlist), 2)
        paid_entry = next(
            item for item in playlist if item["id"] == self.paid_video.slug
        )
        free_entry = next(
            item for item in playlist if item["id"] == self.free_video.slug
        )
        self.assertTrue(paid_entry["isLocked"])
        self.assertFalse(free_entry["isLocked"])
        self.assertEqual(paid_entry["videoKey"], self.paid_video.video_key)
        self.assertEqual(free_entry["videoKey"], self.free_video.video_key)

    def test_retrieves_episode_by_uuid(self):
        response = self.client.get(self.detail_url(str(self.episode.uuid)))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.episode.slug)


class VideoDetailViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.video = Video.objects.create(
            title="Detail Video",
            cdn=Video.CDNChoices.VIMEO,
            price=15,
            duration=240,
            video_key="detail-key",
            poster_url="https://example.com/poster.png",
            description="Test description",
        )

    def detail_url(self, video_id):
        return reverse("video_detail", kwargs={"video_id": video_id})

    def test_retrieves_video_by_slug(self):
        response = self.client.get(self.detail_url(self.video.slug))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.video.slug)
        self.assertEqual(response.data["poster"], self.video.poster_url)
        self.assertTrue(response.data["isLocked"])
        self.assertEqual(response.data["videoKey"], self.video.video_key)
        self.assertEqual(response.data["cdn"], self.video.get_cdn_display())

    def test_retrieves_video_by_uuid(self):
        response = self.client.get(self.detail_url(str(self.video.uuid)))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.video.slug)


class VideoURLViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = MBUser.objects.create_user(
            email="viewer@example.com",
            username="viewer@example.com",
            password="strong-pass",
        )
        team = Team.objects.create(name="Playback Team", slug="playback-team")
        self.site = Site.objects.get_current()
        show = Show.objects.create(
            team=team, site=self.site, title="Playback Show", description="Desc"
        )
        season = Season.objects.create(show=show, order=1, title="S1")
        self.episode = Episode.objects.create(
            show=show,
            season=season,
            order=1,
            title="Episode 1",
            description="Episode description",
        )
        self.free_video = Video.objects.create(
            title="Free Video",
            cdn=Video.CDNChoices.YOUTUBE,
            price=0,
            video_key="free-key",
        )
        self.paid_video = Video.objects.create(
            title="Paid Video",
            cdn=Video.CDNChoices.S3_MEDIA_BUCKET,
            price=25,
            video_key="paid-key",
        )
        self.episode.playlist.add(self.free_video, self.paid_video)

    def playback_url(self, video_id: str) -> str:
        return reverse("video_url", kwargs={"video_id": video_id})

    def test_free_video_returns_video_url_and_cdn(self):
        response = self.client.get(self.playback_url(self.free_video.slug))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.free_video.video_key, response.data.get("videoUrl", ""))
        self.assertEqual(response.data.get("cdn"), "youtube")

    def test_paid_video_requires_login(self):
        response = self.client.get(self.playback_url(self.paid_video.slug))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data.get("detail"), "Authentication required.")

    def test_paid_video_without_receipt_returns_payment_required(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(self.playback_url(self.paid_video.slug))

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(response.data.get("creditsCost"), self.paid_video.price)

    def test_paid_video_with_receipt_allows_access(self):
        """
        Authenticated users with a valid receipt for the video should receive playback info.
        """

        self.client.force_authenticate(self.user)
        VideoReceipt.objects.create(
            user=self.user,
            video=self.paid_video,
            episode=self.episode,
            expiration_date=timezone.now() + timedelta(days=1),
        )

        response = self.client.get(self.playback_url(self.paid_video.slug))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_url = f"http://testserver{reverse('hls_playlist', kwargs={'video_id': str(self.paid_video.uuid)})}"
        self.assertEqual(response.data.get("videoUrl"), expected_url)
        self.assertEqual(response.data.get("cdn"), "s3")

    def test_paid_video_with_expired_receipt_still_locked(self):
        self.client.force_authenticate(self.user)
        VideoReceipt.objects.create(
            user=self.user,
            video=self.paid_video,
            episode=self.episode,
            expiration_date=timezone.now() - timedelta(days=1),
        )

        response = self.client.get(self.playback_url(self.paid_video.slug))

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(response.data.get("creditsCost"), self.paid_video.price)


_CF_TEST_SETTINGS = dict(
    CLOUDFRONT_DOMAIN="cdn.example.com",
    CLOUDFRONT_KEY_PAIR_ID="KTEST123",
    CLOUDFRONT_PRIVATE_KEY="fake-pem",
    CLOUDFRONT_SIGNED_COOKIE_TTL=3600,
    CLOUDFRONT_COOKIE_DOMAIN="",
)

_FAKE_CF_COOKIES = {
    "CloudFront-Policy": "fake-policy",
    "CloudFront-Signature": "fake-sig",
    "CloudFront-Key-Pair-Id": "KTEST123",
}


class SignedPlaylistViewTests(TestCase):
    """
    SignedPlaylistView issues CloudFront signed cookies scoped to the video's
    HLS directory and redirects to master.m3u8 on CloudFront.
    """

    def setUp(self):
        self.client = APIClient()
        self.video_uuid = uuid.UUID("d2774383-7689-4061-aedd-56db83b727d4")
        self.paid_video_uuid = uuid.UUID("bc6d22f0-f26f-441e-849f-4f84041ee1b8")
        self.free_s3_video = Video.objects.create(
            title="Free HLS Video",
            cdn=Video.CDNChoices.S3_MEDIA_BUCKET,
            price=0,
            video_key="hls-key",
            uuid=self.video_uuid,
        )
        self.paid_s3_video = Video.objects.create(
            title="Paid HLS Video",
            cdn=Video.CDNChoices.S3_MEDIA_BUCKET,
            price=20,
            video_key="hls-key-paid",
            uuid=self.paid_video_uuid,
        )
        self.user = MBUser.objects.create_user(
            email="hls@example.com",
            username="hls@example.com",
            password="strong-pass",
        )
        site = Site.objects.get_current()
        team = Team.objects.create(name="HLS Team", slug="hls-team")
        show = Show.objects.create(
            team=team, site=site, title="HLS Show", description="Desc"
        )
        season = Season.objects.create(show=show, order=1, title="S1")
        self.episode = Episode.objects.create(
            show=show, season=season, order=1, title="Ep 1", description="Desc"
        )
        self.episode.playlist.add(self.paid_s3_video)

    def hls_url(self, video_id: str) -> str:
        return reverse("hls_playlist", kwargs={"video_id": video_id})

    # ── Validation ─────────────────────────────────────────────────────────────

    def test_requires_valid_uuid(self):
        response = self.client.get(self.hls_url("not-a-uuid"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("UUID", response.data.get("detail", ""))

    def test_unknown_uuid_returns_not_found(self):
        response = self.client.get(self.hls_url(str(uuid.uuid4())))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cf_not_configured_returns_503(self):
        with override_settings(
            CLOUDFRONT_DOMAIN="", CLOUDFRONT_KEY_PAIR_ID="", CLOUDFRONT_PRIVATE_KEY=""
        ):
            response = self.client.get(self.hls_url(str(self.video_uuid)))

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    # ── Free video ─────────────────────────────────────────────────────────────

    @override_settings(**_CF_TEST_SETTINGS)
    def test_free_video_issues_cookies_and_redirects(self):
        with patch(
            "shows.api.views._generate_cf_signed_cookies",
            return_value=_FAKE_CF_COOKIES,
        ):
            response = self.client.get(self.hls_url(str(self.video_uuid)))

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            response["Location"],
            f"https://cdn.example.com/videos/{self.video_uuid}/hls/master.m3u8",
        )
        self.assertEqual(response.cookies["CloudFront-Policy"].value, "fake-policy")
        self.assertEqual(response.cookies["CloudFront-Signature"].value, "fake-sig")
        self.assertEqual(response.cookies["CloudFront-Key-Pair-Id"].value, "KTEST123")

    @override_settings(**_CF_TEST_SETTINGS)
    def test_free_video_cookie_scope_covers_hls_directory(self):
        """_generate_cf_signed_cookies must be called with a wildcard covering the HLS dir."""
        with patch(
            "shows.api.views._generate_cf_signed_cookies",
            return_value=_FAKE_CF_COOKIES,
        ) as mock_sign:
            self.client.get(self.hls_url(str(self.video_uuid)))

        _, _, resource, _ = mock_sign.call_args.args
        self.assertEqual(
            resource,
            f"https://cdn.example.com/videos/{self.video_uuid}/hls/*",
        )

    # ── Paid video ─────────────────────────────────────────────────────────────

    @override_settings(**_CF_TEST_SETTINGS)
    def test_paid_video_requires_auth(self):
        response = self.client.get(self.hls_url(str(self.paid_video_uuid)))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(**_CF_TEST_SETTINGS)
    def test_paid_video_without_receipt_returns_402(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(self.hls_url(str(self.paid_video_uuid)))

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    @override_settings(**_CF_TEST_SETTINGS)
    def test_paid_video_with_receipt_issues_cookies_and_redirects(self):
        self.client.force_authenticate(self.user)
        VideoReceipt.objects.create(
            user=self.user,
            video=self.paid_s3_video,
            episode=self.episode,
            expiration_date=timezone.now() + timedelta(days=1),
        )

        with patch(
            "shows.api.views._generate_cf_signed_cookies",
            return_value=_FAKE_CF_COOKIES,
        ):
            response = self.client.get(self.hls_url(str(self.paid_video_uuid)))

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            response["Location"],
            f"https://cdn.example.com/videos/{self.paid_video_uuid}/hls/master.m3u8",
        )

    @override_settings(**_CF_TEST_SETTINGS)
    def test_paid_video_with_expired_receipt_returns_402(self):
        self.client.force_authenticate(self.user)
        VideoReceipt.objects.create(
            user=self.user,
            video=self.paid_s3_video,
            episode=self.episode,
            expiration_date=timezone.now() - timedelta(days=1),
        )

        response = self.client.get(self.hls_url(str(self.paid_video_uuid)))

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)


class VideoPurchaseViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = MBUser.objects.create_user(
            email="buyer@example.com",
            username="buyer@example.com",
            password="strong-pass",
        )
        team = Team.objects.create(name="Purchase Team", slug="purchase-team")
        self.site = Site.objects.get_current()
        show = Show.objects.create(
            team=team, site=self.site, title="Show", description="Desc"
        )
        season = Season.objects.create(show=show, order=1, title="S1")

        self.free_video = Video.objects.create(
            title="Free Chapter",
            cdn=Video.CDNChoices.VIMEO,
            price=0,
            video_key="free-key",
        )
        self.paid_video = Video.objects.create(
            title="Paid Chapter",
            cdn=Video.CDNChoices.VIMEO,
            price=10,
            video_key="paid-key",
        )
        self.unlinked_video = Video.objects.create(
            title="Detached",
            cdn=Video.CDNChoices.VIMEO,
            price=5,
            video_key="detached-key",
        )

        self.episode = Episode.objects.create(
            show=show,
            season=season,
            order=1,
            title="Episode 1",
            description="Episode description",
        )
        self.episode.playlist.add(self.free_video, self.paid_video)

    def purchase_url(self, video_id: str) -> str:
        return reverse("video_purchase", kwargs={"video_id": video_id})

    def test_requires_authentication(self):
        response = self.client.post(self.purchase_url(self.free_video.slug))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_video_without_episode(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(self.purchase_url(self.unlinked_video.slug))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not associated with an episode", response.data["detail"])

    def test_free_video_creates_receipt_and_returns_balance(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(self.purchase_url(self.free_video.slug))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["balance"], 0)
        self.assertTrue(
            VideoReceipt.objects.filter(
                user=self.user, video=self.free_video, episode=self.episode
            ).exists()
        )
        self.assertTrue(Wallet.objects.filter(user=self.user).exists())

    def test_existing_valid_receipt_returns_unlocked(self):
        wallet = Wallet.objects.create(user=self.user, balance=3, site=self.site)
        VideoReceipt.objects.create(
            user=self.user,
            video=self.paid_video,
            episode=self.episode,
            expiration_date=timezone.now() + timedelta(days=1),
        )
        self.client.force_authenticate(self.user)

        response = self.client.post(self.purchase_url(self.paid_video.slug))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"], "Existing Valid Purchase. Video unlocked."
        )
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 3)

    def test_insufficient_funds_returns_payment_required(self):
        Wallet.objects.create(user=self.user, balance=2, site=self.site)
        self.client.force_authenticate(self.user)

        response = self.client.post(self.purchase_url(self.paid_video.slug))

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(response.data["price"], self.paid_video.price)
        self.assertEqual(response.data["balance"], 2)
        self.assertFalse(
            VideoReceipt.objects.filter(
                user=self.user, video=self.paid_video, episode=self.episode
            ).exists()
        )

    def test_successful_purchase_deducts_balance_and_creates_receipt(self):
        wallet = Wallet.objects.create(user=self.user, balance=20, site=self.site)
        self.client.force_authenticate(self.user)

        response = self.client.post(self.purchase_url(self.paid_video.slug))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"], "Purchase successful. Video unlocked."
        )
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 10)
        self.assertTrue(
            VideoReceipt.objects.filter(
                user=self.user, video=self.paid_video, episode=self.episode
            ).exists()
        )


class VideoSerializerLockingTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = MBUser.objects.create_user(
            email="serialize@example.com",
            username="serialize@example.com",
            password="strong-pass",
        )
        team = Team.objects.create(name="Serializer Team", slug="serializer-team")
        self.site = Site.objects.get_current()
        show = Show.objects.create(
            team=team, site=self.site, title="Show", description="Desc"
        )
        season = Season.objects.create(show=show, order=1, title="S1")
        self.video = Video.objects.create(
            title="Paid Chapter",
            cdn=Video.CDNChoices.VIMEO,
            price=5,
            video_key="paid-key",
        )
        self.episode = Episode.objects.create(
            show=show,
            season=season,
            order=1,
            title="Episode 1",
            description="Episode description",
        )
        self.episode.playlist.add(self.video)

    def serialize(self, user=None):
        request = self.factory.get("/")
        request.user = user or AnonymousUser()
        return VideoSerializer(self.video, context={"request": request}).data

    def test_paid_video_locked_for_anonymous(self):
        data = self.serialize()

        self.assertTrue(data["isLocked"])

    def test_paid_video_unlocked_with_valid_receipt(self):
        VideoReceipt.objects.create(
            user=self.user,
            video=self.video,
            episode=self.episode,
            expiration_date=timezone.now() + timedelta(days=1),
        )

        data = self.serialize(user=self.user)

        self.assertFalse(data["isLocked"])

    def test_paid_video_locked_when_receipt_expired(self):
        VideoReceipt.objects.create(
            user=self.user,
            video=self.video,
            episode=self.episode,
            expiration_date=timezone.now() - timedelta(days=1),
        )

        data = self.serialize(user=self.user)

        self.assertTrue(data["isLocked"])


# ── Chapter Playback Event endpoint ───────────────────────────────────────────


class ChapterPlaybackEventViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = MBUser.objects.create_user(
            email="tracker@example.com",
            username="tracker@example.com",
            password="strong-pass",
        )
        team = Team.objects.create(name="Tracker Team", slug="tracker-team")
        self.site = Site.objects.get_current()
        show = Show.objects.create(
            team=team, site=self.site, title="Tracker Show", description="Desc"
        )
        season = Season.objects.create(show=show, order=1, title="S1")
        self.video = Video.objects.create(
            title="Tracked Chapter",
            cdn=Video.CDNChoices.S3_MEDIA_BUCKET,
            price=5,
            duration=180,
            video_key="tracked-key",
        )
        self.episode = Episode.objects.create(
            show=show,
            season=season,
            order=1,
            title="Episode 1",
            description="Desc",
        )
        self.episode.playlist.add(self.video)
        self.url = reverse("chapter_playback_event")

    def _payload(self, event_type="chapter.started", **kwargs):
        base = {
            "event_type": event_type,
            "video_id": self.video.slug,
            "session_id": "test-session-abc",
            "position_seconds": 0,
        }
        base.update(kwargs)
        return base

    def test_unauthenticated_returns_401(self):
        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_event_type_returns_400(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            self.url, self._payload(event_type="chapter.exploded"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid event_type", response.data["detail"])

    def test_missing_video_id_returns_400(self):
        self.client.force_authenticate(self.user)
        payload = self._payload()
        del payload["video_id"]

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("video_id", response.data["detail"])

    def test_missing_session_id_returns_400(self):
        self.client.force_authenticate(self.user)
        payload = self._payload()
        del payload["session_id"]

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("session_id", response.data["detail"])

    def test_valid_event_returns_202(self):
        self.client.force_authenticate(self.user)

        with patch("shows.api.views.emit"):
            response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_emit_fires_to_analytics_topic(self):
        self.client.force_authenticate(self.user)

        with patch("shows.api.views.emit") as mock_emit:
            self.client.post(self.url, self._payload(), format="json")

        mock_emit.assert_called_once()
        topic_arg = mock_emit.call_args[0][0]
        self.assertEqual(topic_arg, "analytics")

    def test_chapter_started_sets_watch_started_at_and_expiry(self):
        receipt = VideoReceipt.objects.create(
            user=self.user, video=self.video, episode=self.episode
        )
        self.assertIsNone(receipt.watch_started_at)
        self.assertIsNone(receipt.expiration_date)

        self.client.force_authenticate(self.user)
        with patch("shows.api.views.emit"):
            self.client.post(self.url, self._payload("chapter.started"), format="json")

        receipt.refresh_from_db()
        self.assertIsNotNone(receipt.watch_started_at)
        self.assertIsNotNone(receipt.expiration_date)
        window = receipt.expiration_date - receipt.watch_started_at
        self.assertAlmostEqual(window.total_seconds(), 24 * 3600, delta=5)

    def test_chapter_started_does_not_reset_existing_watch_started_at(self):
        original_start = timezone.now() - timedelta(hours=2)
        receipt = VideoReceipt.objects.create(
            user=self.user,
            video=self.video,
            episode=self.episode,
            watch_started_at=original_start,
            expiration_date=original_start + timedelta(hours=24),
        )

        self.client.force_authenticate(self.user)
        with patch("shows.api.views.emit"):
            self.client.post(self.url, self._payload("chapter.started"), format="json")

        receipt.refresh_from_db()
        self.assertAlmostEqual(
            receipt.watch_started_at.timestamp(),
            original_start.timestamp(),
            delta=1,
        )

    def test_chapter_completed_returns_202(self):
        self.client.force_authenticate(self.user)

        with patch("shows.api.views.emit"):
            response = self.client.post(
                self.url,
                self._payload(
                    "chapter.completed", position_seconds=180, percent_complete=100.0
                ),
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_chapter_started_does_not_affect_other_users_receipts(self):
        other_user = MBUser.objects.create_user(
            email="other@example.com",
            username="other@example.com",
            password="pass",
        )
        other_receipt = VideoReceipt.objects.create(
            user=other_user, video=self.video, episode=self.episode
        )

        self.client.force_authenticate(self.user)
        with patch("shows.api.views.emit"):
            self.client.post(self.url, self._payload("chapter.started"), format="json")

        other_receipt.refresh_from_db()
        self.assertIsNone(other_receipt.watch_started_at)


# ── VideoPurchase — WalletTransaction + event emission ────────────────────────


class VideoPurchaseAuditTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = MBUser.objects.create_user(
            email="audit-buyer@example.com",
            username="audit-buyer@example.com",
            password="strong-pass",
        )
        team = Team.objects.create(name="Audit Team", slug="audit-team")
        self.site = Site.objects.get_current()
        self.show = Show.objects.create(
            team=team, site=self.site, title="Audit Show", description="Desc"
        )
        season = Season.objects.create(show=self.show, order=1, title="S1")
        self.paid_video = Video.objects.create(
            title="Audit Chapter",
            cdn=Video.CDNChoices.VIMEO,
            price=10,
            video_key="audit-paid-key",
        )
        self.episode = Episode.objects.create(
            show=self.show,
            season=season,
            order=1,
            title="Episode 1",
            description="Desc",
        )
        self.episode.playlist.add(self.paid_video)
        self.client.force_authenticate(self.user)

    def _purchase(self):
        return self.client.post(
            reverse("video_purchase", kwargs={"video_id": self.paid_video.slug})
        )

    def _wallet(self, balance=20):
        return Wallet.objects.create(
            user=self.user,
            balance=balance,
            site=self.site,
            credit_type=CreditTypes.CREDIT,
        )

    def test_successful_purchase_creates_wallet_transaction(self):
        wallet = self._wallet(balance=20)

        with patch("shows.api.views.emit"):
            response = self._purchase()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tx = WalletTransaction.objects.get(wallet=wallet)
        self.assertEqual(tx.amount, -self.paid_video.price)
        self.assertEqual(tx.balance_after, 10)
        self.assertEqual(
            tx.transaction_type, WalletTransaction.TransactionType.VIDEO_UNLOCK
        )
        self.assertEqual(tx.reference_type, "video_receipt")
        self.assertEqual(tx.metadata["video_id"], str(self.paid_video.uuid))
        self.assertEqual(tx.metadata["episode_id"], str(self.episode.uuid))

    def test_insufficient_funds_creates_no_wallet_transaction(self):
        wallet = self._wallet(balance=2)

        with patch("shows.api.views.emit"):
            response = self._purchase()

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertFalse(WalletTransaction.objects.filter(wallet=wallet).exists())

    def test_successful_purchase_emits_chapter_unlocked_to_revenue_topic(self):
        self._wallet(balance=20)

        with patch("shows.api.views.emit") as mock_emit:
            self._purchase()

        mock_emit.assert_called_once()
        topic_arg, event_arg = mock_emit.call_args[0]
        self.assertEqual(topic_arg, "revenue")
        self.assertEqual(event_arg.event_type, "chapter.unlocked")
        self.assertEqual(event_arg.video_id, str(self.paid_video.uuid))
        self.assertEqual(event_arg.episode_id, str(self.episode.uuid))
        self.assertEqual(event_arg.credits_spent, self.paid_video.price)
        self.assertEqual(event_arg.unlock_method, "credits")

    def test_purchase_snapshots_default_rev_share_rate_when_no_deal(self):
        self._wallet(balance=20)

        with patch("shows.api.views.emit") as mock_emit:
            self._purchase()

        _, event_arg = mock_emit.call_args[0]
        self.assertEqual(event_arg.rev_share_rate, "0.70")

    def test_purchase_snapshots_active_rev_share_deal_rate(self):
        self._wallet(balance=20)
        RevShareDeal.objects.create(
            show=self.show,
            creator_rate=Decimal("0.80"),
            effective_from=timezone.now() - timedelta(days=30),
            effective_to=None,
        )

        with patch("shows.api.views.emit") as mock_emit:
            self._purchase()

        _, event_arg = mock_emit.call_args[0]
        # DecimalField(decimal_places=4) serialises 0.80 → "0.8000" via str()
        self.assertEqual(Decimal(event_arg.rev_share_rate), Decimal("0.80"))

    def test_free_video_creates_no_wallet_transaction(self):
        free_video = Video.objects.create(
            title="Free Chapter",
            cdn=Video.CDNChoices.VIMEO,
            price=0,
            video_key="free-audit",
        )
        self.episode.playlist.add(free_video)

        with patch("shows.api.views.emit"):
            response = self.client.post(
                reverse("video_purchase", kwargs={"video_id": free_video.slug})
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            WalletTransaction.objects.filter(wallet__user=self.user).exists()
        )

    def test_free_video_emits_chapter_unlocked_with_free_unlock_method(self):
        free_video = Video.objects.create(
            title="Free Chapter 2",
            cdn=Video.CDNChoices.VIMEO,
            price=0,
            video_key="free-audit-2",
        )
        self.episode.playlist.add(free_video)

        with patch("shows.api.views.emit") as mock_emit:
            self.client.post(
                reverse("video_purchase", kwargs={"video_id": free_video.slug})
            )

        mock_emit.assert_called_once()
        topic_arg, event_arg = mock_emit.call_args[0]
        self.assertEqual(topic_arg, "revenue")
        self.assertEqual(event_arg.unlock_method, "free")
        self.assertEqual(event_arg.credits_spent, 0)


# ── RevShareDeal model ─────────────────────────────────────────────────────────


class RevShareDealTests(TestCase):
    def setUp(self):
        team = Team.objects.create(name="Deal Team", slug="deal-team")
        site = Site.objects.get_current()
        self.show = Show.objects.create(
            team=team, site=site, title="Deal Show", description="Desc"
        )

    def test_default_rate_returned_when_no_deal_exists(self):
        rate = RevShareDeal.current_rate_for_show(self.show)

        self.assertEqual(rate, Decimal("0.70"))

    def test_active_deal_rate_returned(self):
        RevShareDeal.objects.create(
            show=self.show,
            creator_rate=Decimal("0.85"),
            effective_from=timezone.now() - timedelta(days=10),
            effective_to=None,
        )

        rate = RevShareDeal.current_rate_for_show(self.show)

        self.assertEqual(rate, Decimal("0.85"))

    def test_expired_deal_falls_back_to_default(self):
        RevShareDeal.objects.create(
            show=self.show,
            creator_rate=Decimal("0.85"),
            effective_from=timezone.now() - timedelta(days=30),
            effective_to=timezone.now() - timedelta(days=1),
        )

        rate = RevShareDeal.current_rate_for_show(self.show)

        self.assertEqual(rate, Decimal("0.70"))

    def test_new_active_deal_supersedes_expired_deal(self):
        RevShareDeal.objects.create(
            show=self.show,
            creator_rate=Decimal("0.75"),
            effective_from=timezone.now() - timedelta(days=60),
            effective_to=timezone.now() - timedelta(days=1),
        )
        RevShareDeal.objects.create(
            show=self.show,
            creator_rate=Decimal("0.80"),
            effective_from=timezone.now() - timedelta(days=1),
            effective_to=None,
        )

        rate = RevShareDeal.current_rate_for_show(self.show)

        self.assertEqual(rate, Decimal("0.80"))

    def test_deal_for_different_show_does_not_affect_result(self):
        other_team = Team.objects.create(name="Other Team", slug="other-deal-team")
        other_show = Show.objects.create(
            team=other_team,
            site=Site.objects.get_current(),
            title="Other Show",
            description="Desc",
        )
        RevShareDeal.objects.create(
            show=other_show,
            creator_rate=Decimal("0.90"),
            effective_from=timezone.now() - timedelta(days=1),
            effective_to=None,
        )

        rate = RevShareDeal.current_rate_for_show(self.show)

        self.assertEqual(rate, Decimal("0.70"))


class ShowsSearchTests(TestCase):
    """GET /api/shows/search — real queryset, SearchResultSerializer shape."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("shows_search")
        self.site = Site.objects.get_current()
        self.team = Team.objects.create(name="Search Team", slug="search-team")

        self.show_a = Show.objects.create(
            team=self.team,
            site=self.site,
            title="Dragon Tales",
            description="A story about dragons.",
            slug="dragon-tales",
            active=True,
        )
        self.show_b = Show.objects.create(
            team=self.team,
            site=self.site,
            title="Space Opera",
            description="Epic adventures in space.",
            slug="space-opera",
            active=True,
        )
        self.inactive_show = Show.objects.create(
            team=self.team,
            site=self.site,
            title="Hidden Gem",
            description="Never shown.",
            slug="hidden-gem",
            active=False,
        )
        self.genre_tag = Tag.objects.create(
            name="Fantasy", slug="fantasy", tagtype=Tag.TagType.GENRE
        )
        self.show_a.tags.add(self.genre_tag)

    def test_empty_query_returns_all_active_shows(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        slugs = [r["id"] for r in resp.data]
        self.assertIn("dragon-tales", slugs)
        self.assertIn("space-opera", slugs)
        self.assertNotIn("hidden-gem", slugs)

    def test_query_filters_by_title(self):
        resp = self.client.get(self.url, {"q": "Dragon"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["id"], "dragon-tales")

    def test_query_filters_by_description(self):
        resp = self.client.get(self.url, {"q": "adventures in space"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["id"], "space-opera")

    def test_query_filters_by_tag(self):
        resp = self.client.get(self.url, {"q": "Fantasy"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["id"], "dragon-tales")

    def test_inactive_shows_excluded(self):
        resp = self.client.get(self.url, {"q": "Hidden"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_no_query_match_returns_empty(self):
        resp = self.client.get(self.url, {"q": "xyznonexistent"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_response_shape_matches_search_result_contract(self):
        resp = self.client.get(self.url, {"q": "Dragon"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        item = resp.data[0]
        expected_keys = {
            "id",
            "title",
            "type",
            "thumbnail",
            "description",
            "creator",
            "rating",
            "views",
            "category",
            "tags",
            "releaseYear",
            "isPremium",
            "price",
        }
        self.assertTrue(expected_keys.issubset(set(item.keys())))
        self.assertEqual(item["id"], "dragon-tales")
        self.assertIsInstance(item["tags"], list)
        self.assertIsInstance(item["rating"], (int, float))
        self.assertIsInstance(item["releaseYear"], int)
