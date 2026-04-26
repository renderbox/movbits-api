from django.contrib.auth import get_user_model
from django.test import TestCase

from shows.models import Video

from ..models import BatchStatus, UploadBatch, UploadBatchFile
from ..api.views import _finalize_video, _pick_entry_point

User = get_user_model()


def make_video(title="Video 1", cdn=Video.CDNChoices.VIMEO):
    return Video.objects.create(title=title, cdn=cdn)


def make_batch(video, staff_user, name="Test Batch"):
    return UploadBatch.objects.create(
        video=video,
        batch_name=name,
        created_by=staff_user,
        status=BatchStatus.PENDING,
    )


def add_file(batch, relative_path, filename=None):
    filename = filename or relative_path.split("/")[-1]
    hls_dir = batch.video.get_video_hls_path(version=batch.video.version)
    return UploadBatchFile.objects.create(
        batch=batch,
        filename=filename,
        relative_path=relative_path,
        s3_key=f"{hls_dir}{relative_path}",
        size=1024,
        content_type="video/mp2t",
    )


class PickEntryPointTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="x", is_staff=True
        )
        self.video = make_video()
        self.batch = make_batch(self.video, self.staff)

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
        self.assertEqual(_pick_entry_point(self.batch), "index.m3u8")


class FinalizeVideoTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="x", is_staff=True
        )
        self.video = make_video()
        self.batch = make_batch(self.video, self.staff)

    def test_sets_cdn_to_s3(self):
        add_file(self.batch, "index.m3u8")
        _finalize_video(self.batch)
        self.video.refresh_from_db()
        self.assertEqual(self.video.cdn, Video.CDNChoices.S3_MEDIA_BUCKET)

    def test_sets_video_key_to_entry_point(self):
        add_file(self.batch, "index.m3u8")
        add_file(self.batch, "segment0.ts")
        _finalize_video(self.batch)
        self.video.refresh_from_db()
        self.assertEqual(self.video.video_key, "index.m3u8")

    def test_video_key_none_when_no_m3u8(self):
        add_file(self.batch, "segment0.ts")
        _finalize_video(self.batch)
        self.video.refresh_from_db()
        self.assertIsNone(self.video.video_key)
