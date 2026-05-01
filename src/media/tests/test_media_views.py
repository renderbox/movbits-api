from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from shows.models import Video

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


def make_video(title="Video 1", cdn=Video.CDNChoices.VIMEO):
    return Video.objects.create(title=title, cdn=cdn)


def make_batch(video, user, name="Test Batch", batch_status=BatchStatus.PENDING):
    return UploadBatch.objects.create(
        video=video, batch_name=name, created_by=user, status=batch_status
    )


def add_file(batch, relative_path, file_status=FileStatus.PENDING):
    filename = relative_path.split("/")[-1]
    hls_dir = batch.video.get_video_hls_path(version=batch.video.version)
    return UploadBatchFile.objects.create(
        batch=batch,
        filename=filename,
        relative_path=relative_path,
        s3_key=f"{hls_dir}{relative_path}",
        size=1024,
        content_type=(
            "video/mp2t" if relative_path.endswith(".ts") else "application/x-mpegURL"
        ),
        status=file_status,
    )


MANIFEST = [
    {
        "filename": "index.m3u8",
        "relative_path": "index.m3u8",
        "size": 512,
        "content_type": "application/x-mpegURL",
    },
    {
        "filename": "seg0.ts",
        "relative_path": "seg0.ts",
        "size": 2048,
        "content_type": "video/mp2t",
    },
]


# ── create_upload_batch ───────────────────────────────────────────────────────


class CreateUploadBatchTests(APITestCase):
    def setUp(self):
        self.staff = make_user("staff", is_staff=True)
        self.user = make_user("user", is_staff=False)
        self.video = make_video()
        self.url = reverse("media_create_batch")

    def _post(self, data):
        with patch(
            "media.api.views._presigned_put_url", return_value=FAKE_PRESIGNED_URL
        ):
            return self.client.post(self.url, data, format="json")

    def test_unauthenticated_returns_403(self):
        response = self._post({"video_uuid": str(self.video.uuid), "files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_returns_403(self):
        self.client.force_authenticate(self.user)
        response = self._post({"video_uuid": str(self.video.uuid), "files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_video_uuid_returns_400(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_files_returns_400(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"video_uuid": str(self.video.uuid), "files": []})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_video_uuid_returns_404(self):
        self.client.force_authenticate(self.staff)
        response = self._post(
            {"video_uuid": "00000000-0000-0000-0000-000000000000", "files": MANIFEST}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_creates_batch_and_returns_201(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"video_uuid": str(self.video.uuid), "files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(len(response.data["files"]), 2)

    def test_response_includes_upload_url(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"video_uuid": str(self.video.uuid), "files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        for f in response.data["files"]:
            self.assertEqual(f["upload_url"], FAKE_PRESIGNED_URL)

    def test_s3_key_uses_video_hls_dir(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"video_uuid": str(self.video.uuid), "files": MANIFEST})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        batch_id = response.data["id"]
        files = UploadBatchFile.objects.filter(batch_id=batch_id)
        expected_prefix = self.video.get_video_hls_path(version=self.video.version)
        for f in files:
            self.assertTrue(f.s3_key.startswith(expected_prefix))

    def test_batch_name_defaults_to_cli_upload(self):
        self.client.force_authenticate(self.staff)
        response = self._post({"video_uuid": str(self.video.uuid), "files": MANIFEST})
        self.assertEqual(response.data["batch_name"], "CLI Upload")

    def test_batch_name_can_be_set(self):
        self.client.force_authenticate(self.staff)
        response = self._post(
            {
                "video_uuid": str(self.video.uuid),
                "files": MANIFEST,
                "batch_name": "Season 2 Upload",
            }
        )
        self.assertEqual(response.data["batch_name"], "Season 2 Upload")


# ── upload_batch_detail ───────────────────────────────────────────────────────


class UploadBatchDetailTests(APITestCase):
    def setUp(self):
        self.staff = make_user("staff", is_staff=True)
        self.user = make_user("user", is_staff=False)
        self.video = make_video("Video 2")
        self.batch = make_batch(self.video, self.staff)
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
        url = reverse(
            "media_batch_detail",
            kwargs={"batch_id": "00000000-0000-0000-0000-000000000000"},
        )
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
        self.video = make_video("Video 3")
        self.batch = make_batch(self.video, self.staff)
        self.m3u8 = add_file(self.batch, "index.m3u8")
        self.seg = add_file(self.batch, "seg0.ts")

    def _complete_url(self, file_obj):
        return reverse(
            "media_complete_file",
            kwargs={
                "batch_id": self.batch.id,
                "file_id": file_obj.id,
            },
        )

    def test_unauthenticated_returns_403(self):
        response = self.client.post(self._complete_url(self.m3u8))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_returns_403(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(self._complete_url(self.m3u8))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_file_returns_404(self):
        self.client.force_authenticate(self.staff)
        url = reverse(
            "media_complete_file",
            kwargs={
                "batch_id": self.batch.id,
                "file_id": "00000000-0000-0000-0000-000000000000",
            },
        )
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

    def test_video_finalized_when_batch_complete(self):
        self.client.force_authenticate(self.staff)
        self.client.post(self._complete_url(self.m3u8))
        self.client.post(self._complete_url(self.seg))
        self.video.refresh_from_db()
        self.assertEqual(self.video.cdn, Video.CDNChoices.S3_MEDIA_BUCKET)
        self.assertEqual(self.video.video_key, "index.m3u8")

    def test_video_not_finalized_until_all_files_done(self):
        self.client.force_authenticate(self.staff)
        self.client.post(self._complete_url(self.m3u8))
        self.video.refresh_from_db()
        # Still VIMEO — not finalized yet
        self.assertEqual(self.video.cdn, Video.CDNChoices.VIMEO)


# ── list_uploads ──────────────────────────────────────────────────────────────


class ListUploadsTests(APITestCase):
    def setUp(self):
        self.staff = make_user("staff", is_staff=True)
        self.user = make_user("user", is_staff=False)
        self.video_a = make_video("Video A")
        self.video_b = make_video("Video B")
        self.batch_a = make_batch(self.video_a, self.staff, "Batch A")
        self.batch_b = make_batch(self.video_b, self.staff, "Batch B")
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

    def test_filter_by_video_uuid(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url, {"video_uuid": str(self.video_a.uuid)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["files"]), 2)
        for f in response.data["files"]:
            self.assertEqual(f["video_uuid"], str(self.video_a.uuid))

    def test_filter_by_prefix(self):
        self.client.force_authenticate(self.staff)
        prefix = self.video_a.get_video_hls_path(version=self.video_a.version)
        response = self.client.get(self.url, {"prefix": prefix})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["files"]), 2)

    def test_response_includes_expected_fields(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url)
        f = response.data["files"][0]
        for field in [
            "key",
            "relative_path",
            "filename",
            "size",
            "status",
            "batch_id",
            "video_uuid",
        ]:
            self.assertIn(field, f)
