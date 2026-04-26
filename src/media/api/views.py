import boto3
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from microdrama.models import Chapter

from ..models import BatchStatus, FileStatus, UploadBatch, UploadBatchFile
from .serializers import (
    UploadBatchCreateSerializer,
    UploadBatchSerializer,
    UploadBatchFileSerializer,
)

_PRESIGNED_URL_EXPIRY = 3600  # seconds


def _require_staff(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
    return None


def _get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )


def _presigned_put_url(s3_key, content_type):
    client = _get_s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.AWS_MEDIA_BUCKET_NAME,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=_PRESIGNED_URL_EXPIRY,
    )


def _pick_entry_point(batch):
    """Return the filename of the top-level .m3u8 (the HLS entry point)."""
    m3u8_files = batch.files.filter(filename__endswith=".m3u8").order_by("relative_path")
    # Prefer a root-level .m3u8 (no directory separator in relative_path)
    root_level = [f for f in m3u8_files if "/" not in f.relative_path]
    candidates = root_level or list(m3u8_files)
    return candidates[0].filename if candidates else None


def _finalize_chapter(batch):
    """Set chapter to S3 CDN and mark as transcoded once all files are uploaded."""
    entry_point = _pick_entry_point(batch)
    chapter = batch.chapter
    chapter.cdn = Chapter.CDNChoices.S3_MEDIA_BUCKET
    chapter.video_url = entry_point
    chapter.transcoded = True
    chapter.save(update_fields=["cdn", "video_url", "transcoded"])


# ── Create batch ─────────────────────────────────────────────────────────────


@api_view(["POST"])
def create_upload_batch(request):
    if err := _require_staff(request):
        return err

    chapter_uuid = request.data.get("chapter_uuid")
    if not chapter_uuid:
        return Response({"detail": "chapter_uuid is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        chapter = Chapter.objects.get(uuid=chapter_uuid)
    except Chapter.DoesNotExist:
        return Response({"detail": "Chapter not found."}, status=status.HTTP_404_NOT_FOUND)

    files_data = request.data.get("files", [])
    if not files_data:
        return Response({"detail": "files list is required."}, status=status.HTTP_400_BAD_REQUEST)

    batch = UploadBatch.objects.create(
        chapter=chapter,
        batch_name=request.data.get("batch_name", "CLI Upload"),
        created_by=request.user,
        status=BatchStatus.PENDING,
    )

    file_objs = []
    for f in files_data:
        relative_path = f.get("relative_path") or f.get("filename", "")
        content_type = f.get("content_type") or "application/octet-stream"
        s3_key = f"{chapter.get_hls_dir()}{relative_path}"

        file_obj = UploadBatchFile(
            batch=batch,
            filename=f.get("filename", relative_path.split("/")[-1]),
            relative_path=relative_path,
            s3_key=s3_key,
            size=f.get("size", 0),
            content_type=content_type,
        )
        file_objs.append(file_obj)

    UploadBatchFile.objects.bulk_create(file_objs)

    # Generate presigned PUT URLs and attach to instances for serialization
    for file_obj in file_objs:
        file_obj.upload_url = _presigned_put_url(file_obj.s3_key, file_obj.content_type)

    batch._prefetched_objects_cache = {"files": file_objs}
    return Response(UploadBatchCreateSerializer(batch).data, status=status.HTTP_201_CREATED)


# ── Batch detail ──────────────────────────────────────────────────────────────


@api_view(["GET"])
def upload_batch_detail(request, batch_id):
    if err := _require_staff(request):
        return err

    try:
        batch = UploadBatch.objects.prefetch_related("files").get(pk=batch_id)
    except (UploadBatch.DoesNotExist, ValueError):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response(UploadBatchSerializer(batch).data)


# ── Complete file ─────────────────────────────────────────────────────────────


@api_view(["POST"])
def complete_file_upload(request, batch_id, file_id):
    if err := _require_staff(request):
        return err

    try:
        batch = UploadBatch.objects.get(pk=batch_id)
        file_obj = UploadBatchFile.objects.get(pk=file_id, batch=batch)
    except (UploadBatch.DoesNotExist, UploadBatchFile.DoesNotExist, ValueError):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    file_obj.status = FileStatus.UPLOADED
    file_obj.save(update_fields=["status"])

    # Check if entire batch is done
    pending_count = batch.files.exclude(status=FileStatus.UPLOADED).count()
    if pending_count == 0:
        batch.status = BatchStatus.COMPLETE
        batch.save(update_fields=["status"])
        _finalize_chapter(batch)

    elif batch.status == BatchStatus.PENDING:
        batch.status = BatchStatus.IN_PROGRESS
        batch.save(update_fields=["status"])

    return Response(UploadBatchFileSerializer(file_obj).data)


# ── List uploads ──────────────────────────────────────────────────────────────


@api_view(["GET"])
def list_uploads(request):
    if err := _require_staff(request):
        return err

    qs = UploadBatchFile.objects.select_related("batch__chapter").order_by("-batch__created_at", "relative_path")

    chapter_uuid = request.query_params.get("chapter_uuid")
    if chapter_uuid:
        qs = qs.filter(batch__chapter__uuid=chapter_uuid)

    prefix = request.query_params.get("prefix")
    if prefix:
        qs = qs.filter(s3_key__startswith=prefix)

    files = [
        {
            "key": f.s3_key,
            "relative_path": f.relative_path,
            "filename": f.filename,
            "size": f.size,
            "status": f.status,
            "batch_id": str(f.batch_id),
            "chapter_uuid": str(f.batch.chapter.uuid),
        }
        for f in qs
    ]
    return Response({"files": files})
