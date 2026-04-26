from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from microdrama.models import Chapter, Episode, Series
from team.models import Team

from ..models import BatchStatus, FileStatus, UploadBatch, UploadBatchFile

User = get_user_model()

FAKE_PRESIGNED_URL = "https://s3.amazonaws.com/movbits-media/fake-presigned-url"


def make_user(username, is_staff=False):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="password",
        is_staff=is_staff,
    )


def make_chapter(title="Chapter 1", cdn=Chapter.CDNChoices.VIMEO):
    site = Site.objects.get_or_create(domain="example.com", defaults={"name": "example"})[0]
    # Team.save() always slugifies `name`, so use the title to keep slugs unique.
    team = Team.objects.create(name=f"Team {title}")
    team.sites.add(site)
    series = Series.objects.create(
        title=f"Series {title}", slug=f"series-{title.lower().replace(' ', '-')}",
        description="desc", team=team,
    )
    episode = Episode.objects.create(title="Ep 1", slug="ep-1", series=series, order=1)
    return Chapter.objects.create(title=title, episode=episode, chapter_number=0, cdn=cdn)


def make_batch(chapter, user, name="Test Batch", batch_status=BatchStatus.PENDING):
    return UploadBatch.objects.create(
        chapter=chapter, batch_name=name, created_by=user, status=batch_status
    )


def add_file(batch, relative_path, file_status=FileStatus.PENDING):
    filename = relative_path.split("/")[-1]
    return UploadBatchFile.objects.create(
        batch=batch,
        filename=filename,
        relative_path=relative_path,
        s3_key=f"ch/{batch.chapter.uuid}/video/hls/{relative_path}",
        size=1024,
        content_type="video/mp2t" if relative_path.endswith(".ts") else "application/x-mpegURL",
        status=file_status,
    )


MANIFEST = [
    {"filename": "index.m3u8", "relative_path": "index.m3u8", "size": 512, "content_type": "application/x-mpegURL"},
    {"filename": "seg0.ts", "relative_path": "seg0.ts", "size": 2048, "content_type": "video/mp2t"},
]


# ── create_upload_batch ───────────────────────────────────────────────────────


class CreateUploadBatchTests(APITestCase):
    def setUp(self):
        self.staff = make_user("staff", is_staff=True)
        self.user = make_user("user", is_staff=False)
        self.chapter = make_chapter()
        self.url = reverse("media_create_batch")

    def _post(self, data):
        with patch("media.api.views._presigned_put_url", return_value=FAKE_PRESIGNED_URL):
            return self.client.post(self.url, data, format="json")

    def test_unauthenticated_returns_403(self):
        response = self._post({"chapter_uuid": str(self.chapter.uuid), "files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_returns_403(self):
        self.client.force_authenticate(self.user)
        response = self._post({"chapter_uuid": str(self.chapter.uuid), "files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_chapter_uuid_returns_400(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_files_returns_400(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"chapter_uuid": str(self.chapter.uuid), "files": []})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_chapter_uuid_returns_404(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"chapter_uuid": "00000000-0000-0000-0000-000000000000", "files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_creates_batch_and_returns_201(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"chapter_uuid": str(self.chapter.uuid), "files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(len(response.data["files"]), 2)

    def test_response_includes_upload_url(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"chapter_uuid": str(self.chapter.uuid), "files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        for f in response.data["files"]:
            self.assertEqual(f["upload_url"], FAKE_PRESIGNED_URL)

    def test_s3_key_uses_chapter_hls_dir(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"chapter_uuid": str(self.chapter.uuid), "files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        batch_id = response.data["id"]
        files = UploadBatchFile.objects.filter(batch_id=batch_id)
        expected_prefix = self.chapter.get_hls_dir()
        for f in files:
            self.assertTrue(f.s3_key.startswith(expected_prefix))

    def test_batch_name_defaults_to_cli_upload(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"chapter_uuid": str(self.chapter.uuid), "files": MANIFEST})
        self.assertEqual(response.data["batch_name"], "CLI Upload")

    def test_batch_name_can_be_set(self):
        self.client.force_authenticate(self.staff)
        response = self._post({
            "chapter_uuid": str(self.chapter.uuid),
            "files": MANIFEST,
            "batch_name": "Season 2 Upload",
        })
        self.assertEqual(response.data["batch_name"], "Season 2 Upload")


# ── upload_batch_detail ───────────────────────────────────────────────────────


class UploadBatchDetailTests(APITestCase):
    def setUp(self):
        self.staff = make_user("staff", is_staff=True)
        self.user = make_user("user", is_staff=False)
        self.chapter = make_chapter("Chapter 2")
        self.batch = make_batch(self.chapter, self.staff)
        add_file(self.batch, "index.m3u8")
        self.url = reverse("media_batch_detail", kwargs={"batch_id": self.batch.id})

    def test_unauthenticated_returns_403(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_returns_403(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_batch_id_returns_404(self):
        self.client.force_authenticate(self.staff)
        url = reverse("media_batch_detail", kwargs={"batch_id": "00000000-0000-0000-0000-000000000000"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_batch_with_files(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data["id"]), str(self.batch.id))
        self.assertEqual(len(response.data["files"]), 1)

    def test_response_does_not_include_upload_url(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url)
        self.assertNotIn("upload_url", response.data["files"][0])


# ── complete_file_upload ──────────────────────────────────────────────────────


class CompleteFileUploadTests(APITestCase):
    def setUp(self):
        self.staff = make_user("staff", is_staff=True)
        self.user = make_user("user", is_staff=False)
        self.chapter = make_chapter("Chapter 3")
        self.batch = make_batch(self.chapter, self.staff)
        self.m3u8 = add_file(self.batch, "index.m3u8")
        self.seg = add_file(self.batch, "seg0.ts")

    def _complete_url(self, file_obj):
        return reverse("media_complete_file", kwargs={
            "batch_id": self.batch.id,
            "file_id": file_obj.id,
        })

    def test_unauthenticated_returns_403(self):
        response = self.client.post(self._complete_url(self.m3u8))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_returns_403(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(self._complete_url(self.m3u8))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_file_returns_404(self):
        self.client.force_authenticate(self.staff)
        url = reverse("media_complete_file", kwargs={
            "batch_id": self.batch.id,
            "file_id": "00000000-0000-0000-0000-000000000000",
        })
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_marks_file_as_uploaded(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(self._complete_url(self.m3u8))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.m3u8.refresh_from_db()
        self.assertEqual(self.m3u8.status, FileStatus.UPLOADED)

    def test_batch_transitions_to_in_progress_on_first_file(self):
        self.client.force_authenticate(self.staff)
        self.client.post(self._complete_url(self.m3u8))
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.IN_PROGRESS)

    def test_batch_completes_when_all_files_uploaded(self):
        self.client.force_authenticate(self.staff)
        self.client.post(self._complete_url(self.m3u8))
        self.client.post(self._complete_url(self.seg))
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, BatchStatus.COMPLETE)

    def test_chapter_finalized_when_batch_complete(self):
        self.client.force_authenticate(self.staff)
        self.client.post(self._complete_url(self.m3u8))
        self.client.post(self._complete_url(self.seg))
        self.chapter.refresh_from_db()
        self.assertEqual(self.chapter.cdn, Chapter.CDNChoices.S3_MEDIA_BUCKET)
        self.assertEqual(self.chapter.video_url, "index.m3u8")
        self.assertTrue(self.chapter.transcoded)

    def test_chapter_not_finalized_until_all_files_done(self):
        self.client.force_authenticate(self.staff)
        self.client.post(self._complete_url(self.m3u8))
        self.chapter.refresh_from_db()
        # Still VIMEO — not finalized yet
        self.assertEqual(self.chapter.cdn, Chapter.CDNChoices.VIMEO)


# ── list_uploads ──────────────────────────────────────────────────────────────


class ListUploadsTests(APITestCase):
    def setUp(self):
        self.staff = make_user("staff", is_staff=True)
        self.user = make_user("user", is_staff=False)
        self.chapter_a = make_chapter("Chapter A")
        self.chapter_b = make_chapter("Chapter B")
        self.batch_a = make_batch(self.chapter_a, self.staff, "Batch A")
        self.batch_b = make_batch(self.chapter_b, self.staff, "Batch B")
        add_file(self.batch_a, "index.m3u8")
        add_file(self.batch_a, "seg0.ts")
        add_file(self.batch_b, "index.m3u8")
        self.url = reverse("media_list_uploads")

    def test_unauthenticated_returns_403(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_returns_403(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_all_files_for_staff(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["files"]), 3)

    def test_filter_by_chapter_uuid(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url, {"chapter_uuid": str(self.chapter_a.uuid)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["files"]), 2)
        for f in response.data["files"]:
            self.assertEqual(f["chapter_uuid"], str(self.chapter_a.uuid))

    def test_filter_by_prefix(self):
        self.client.force_authenticate(self.staff)
        prefix = self.chapter_a.get_hls_dir()
        response = self.client.get(self.url, {"prefix": prefix})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["files"]), 2)

    def test_response_includes_expected_fields(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url)
        f = response.data["files"][0]
        for field in ["key", "relative_path", "filename", "size", "status", "batch_id", "chapter_uuid"]:
            self.assertIn(field, f)
