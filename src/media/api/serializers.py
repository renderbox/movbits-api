from rest_framework import serializers

from ..models import UploadBatch, UploadBatchFile


class UploadBatchFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadBatchFile
        fields = [
            "id",
            "filename",
            "relative_path",
            "s3_key",
            "size",
            "content_type",
            "status",
        ]


class UploadBatchFileWithUrlSerializer(UploadBatchFileSerializer):
    upload_url = serializers.CharField()

    class Meta(UploadBatchFileSerializer.Meta):
        fields = UploadBatchFileSerializer.Meta.fields + ["upload_url"]


class UploadBatchSerializer(serializers.ModelSerializer):
    files = UploadBatchFileSerializer(many=True, read_only=True)
    videoUuid = serializers.UUIDField(source="video.uuid", read_only=True)

    class Meta:
        model = UploadBatch
        fields = [
            "id",
            "batch_name",
            "videoUuid",
            "status",
            "created_at",
            "updated_at",
            "files",
        ]


class UploadBatchCreateSerializer(UploadBatchSerializer):
    files = UploadBatchFileWithUrlSerializer(many=True, read_only=True)
