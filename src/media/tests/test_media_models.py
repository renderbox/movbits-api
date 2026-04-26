from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase

from microdrama.models import Chapter, Episode, Series
from team.models import Team

from ..models import BatchStatus, UploadBatch, UploadBatchFile
from ..api.views import _finalize_chapter, _pick_entry_point

User = get_user_model()


def make_chapter(title="Chapter 1", cdn=Chapter.CDNChoices.VIMEO):
    site = Site.objects.get_or_create(domain="example.com", defaults={"name": "example"})[0]
    # Team.save() always slugifies `name`, so use the title to keep slugs unique.
    team = Team.objects.create(name=f"Team {title}")
    team.sites.add(site)
    series = Series.objects.create(
        title="Test Series", slug="test-series", description="desc", team=team
    )
    episode = Episode.objects.create(
        title="Ep 1", slug="ep-1", series=series, order=1
    )
    return Chapter.objects.create(
        title=title, episode=episode, chapter_number=0, cdn=cdn
    )


def make_batch(chapter, staff_user, name="Test Batch"):
    return UploadBatch.objects.create(
        chapter=chapter,
        batch_name=name,
        created_by=staff_user,
        status=BatchStatus.PENDING,
    )


def add_file(batch, relative_path, filename=None):
    filename = filename or relative_path.split("/")[-1]
    return UploadBatchFile.objects.create(
        batch=batch,
        filename=filename,
        relative_path=relative_path,
        s3_key=f"ch/{batch.chapter.uuid}/video/hls/{relative_path}",
        size=1024,
        content_type="video/mp2t",
    )


class PickEntryPointTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="x", is_staff=True
        )
        self.chapter = make_chapter()
        self.batch = make_batch(self.chapter, self.staff)

    def test_returns_none_when_no_m3u8(self):
        add_file(self.batch, "segment0.ts")
        add_file(self.batch, "segment1.ts")
        self.assertIsNone(_pick_entry_point(self.batch))

    def test_returns_root_level_m3u8(self):
        add_file(self.batch, "index.m3u8")
        add_file(self.batch, "segment0.ts")
        self.assertEqual(_pick_entry_point(self.batch), "index.m3u8")

    def test_prefers_root_level_over_nested(self):
        add_file(self.batch, "master.m3u8")
        add_file(self.batch, "720p/index.m3u8")
        self.assertEqual(_pick_entry_point(self.batch), "master.m3u8")

    def test_falls_back_to_nested_when_no_root(self):
        add_file(self.batch, "720p/index.m3u8")
        add_file(self.batch, "1080p/index.m3u8")
        result = _pick_entry_point(self.batch)
        self.assertIn(result, ["index.m3u8"])

    def test_returns_alphabetically_first_when_all_nested(self):
        add_file(self.batch, "1080p/index.m3u8")
        add_file(self.batch, "720p/index.m3u8")
        # ordered by relative_path, so 1080p comes first
        self.assertEqual(_pick_entry_point(self.batch), "index.m3u8")


class FinalizeChapterTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="x", is_staff=True
        )
        self.chapter = make_chapter()
        self.batch = make_batch(self.chapter, self.staff)

    def test_sets_cdn_to_s3(self):
        add_file(self.batch, "index.m3u8")
        _finalize_chapter(self.batch)
        self.chapter.refresh_from_db()
        self.assertEqual(self.chapter.cdn, Chapter.CDNChoices.S3_MEDIA_BUCKET)

    def test_sets_video_url_to_entry_point(self):
        add_file(self.batch, "index.m3u8")
        add_file(self.batch, "segment0.ts")
        _finalize_chapter(self.batch)
        self.chapter.refresh_from_db()
        self.assertEqual(self.chapter.video_url, "index.m3u8")

    def test_sets_transcoded_true(self):
        add_file(self.batch, "index.m3u8")
        _finalize_chapter(self.batch)
        self.chapter.refresh_from_db()
        self.assertTrue(self.chapter.transcoded)

    def test_video_url_none_when_no_m3u8(self):
        add_file(self.batch, "segment0.ts")
        _finalize_chapter(self.batch)
        self.chapter.refresh_from_db()
        self.assertIsNone(self.chapter.video_url)
