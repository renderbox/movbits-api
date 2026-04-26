import uuid

from django.conf import settings
from django.db import models

from microdrama.models import Chapter


class BatchStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETE = "complete", "Complete"
    FAILED = "failed", "Failed"


class FileStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    UPLOADED = "uploaded", "Uploaded"
    FAILED = "failed", "Failed"


class UploadBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="upload_batches",
    )
    batch_name = models.CharField(max_length=255, default="CLI Upload")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="upload_batches",
    )
    status = models.CharField(
        max_length=20,
        choices=BatchStatus.choices,
        default=BatchStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.batch_name} ({self.id})"


class UploadBatchFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        UploadBatch,
        on_delete=models.CASCADE,
        related_name="files",
    )
    filename = models.CharField(max_length=500)
    relative_path = models.CharField(max_length=1000)
    s3_key = models.CharField(max_length=1000)
    size = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=200, default="application/octet-stream")
    status = models.CharField(
        max_length=20,
        choices=FileStatus.choices,
        default=FileStatus.PENDING,
    )

    class Meta:
        ordering = ["relative_path"]

    def __str__(self):
        return self.relative_path
