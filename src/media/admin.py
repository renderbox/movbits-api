from django.contrib import admin

from .models import UploadBatch, UploadBatchFile


class UploadBatchFileInline(admin.TabularInline):
    model = UploadBatchFile
    extra = 0
    readonly_fields = ["id", "s3_key", "status"]


@admin.register(UploadBatch)
class UploadBatchAdmin(admin.ModelAdmin):
    list_display = ["id", "batch_name", "chapter", "created_by", "status", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [UploadBatchFileInline]
