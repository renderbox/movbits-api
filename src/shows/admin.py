import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib import admin, messages

from .models import (
    Episode,
    EpisodeVideo,
    RevShareDeal,
    Season,
    Show,
    Tag,
    Video,
    VideoReceipt,
)


class SeasonInline(admin.StackedInline):
    model = Season
    extra = 0
    fields = ("title", "order", "description", "poster_file", "banner_file", "active")


class EpisodeInline(admin.StackedInline):
    model = Episode
    extra = 0
    fields = (
        "title",
        "season",
        "order",
        "description",
        "poster_file",
        "banner_file",
        "duration",
        "rating_value",
        "rating_count",
        "chapter_count",
        "active",
    )
    filter_horizontal = ("tags",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "season" and getattr(request, "_obj_", None):
            kwargs["queryset"] = Season.objects.filter(show=request._obj_)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Show)
class ShowAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "slug",
        "team",
        "created_at",
        "updated_at",
        "active",
    )
    search_fields = ("title", "team__name")
    list_filter = ("active", "created_at")
    readonly_fields = (
        "slug",
        "uuid",
    )
    filter_horizontal = ("tags",)
    # inlines = (SeasonInline, EpisodeInline)

    def get_formsets_with_inlines(self, request, obj=None):
        # allow inlines to know which show they are attached to
        request._obj_ = obj
        return super().get_formsets_with_inlines(request, obj)


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "show",
        "order",
        "created_at",
        "updated_at",
        "active",
    )
    search_fields = ("title", "show__title")
    list_filter = ("active", "created_at")


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "show",
        "season",
        "created_at",
        "updated_at",
        "active",
        "get_tags",
    )
    search_fields = ("title", "show__title", "season__title")
    list_filter = ("active", "created_at")
    filter_horizontal = ("tags",)
    readonly_fields = (
        "slug",
        "uuid",
    )

    def get_tags(self, obj):
        return ", ".join(tag.name for tag in obj.tags.all())

    get_tags.short_description = "Tags"


@admin.register(EpisodeVideo)
class EpisodeVideoAdmin(admin.ModelAdmin):
    list_display = (
        "playlist",
        "video",
        "order",
        "created_at",
        "updated_at",
        "active",
    )
    search_fields = ("playlist__title", "video__title")
    list_filter = ("active", "created_at")


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "uuid",
        "slug",
        "cdn",
        "price",
        "duration",
        "created_at",
        "updated_at",
        "active",
    )
    search_fields = ("title", "uuid")
    list_filter = ("cdn", "active", "created_at")
    readonly_fields = (
        "slug",
        "uuid",
    )
    actions = ["create_s3_folders"]

    @admin.action(description="Create S3 folder structure for HLS transcoding")
    def create_s3_folders(self, request, queryset):
        bucket = settings.AWS_MEDIA_BUCKET_NAME
        if not bucket:
            self.message_user(
                request,
                "AWS_MEDIA_BUCKET_NAME is not configured.",
                messages.ERROR,
            )
            return

        try:
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )
        except Exception as exc:
            self.message_user(
                request, f"Could not connect to S3: {exc}", messages.ERROR
            )
            return

        folders = ["src/", "hls/"]
        created = []
        errors = []

        for video in queryset:
            video_root = f"videos/{video.uuid}/"
            try:
                for folder in folders:
                    s3.put_object(Bucket=bucket, Key=video_root + folder, Body=b"")
                created.append(f"{video.title} ({video.uuid})")
            except ClientError as exc:
                errors.append(f"{video.title}: {exc.response['Error']['Message']}")

        if created:
            self.message_user(
                request,
                f"S3 folders created for {len(created)} video(s): {', '.join(created)}",
                messages.SUCCESS,
            )
        if errors:
            self.message_user(
                request,
                f"Errors for {len(errors)} video(s): {'; '.join(errors)}",
                messages.ERROR,
            )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "tagtype", "id")
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("slug",)


@admin.register(VideoReceipt)
class VideoReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "video",
        "episode",
        "purchased_at",
        "expiration_date",
    )
    search_fields = ("user__email", "video__title", "episode__title")
    list_filter = ("expiration_date", "purchased_at")


@admin.register(RevShareDeal)
class RevShareDealAdmin(admin.ModelAdmin):
    list_display = (
        "show",
        "creator_rate",
        "effective_from",
        "effective_to",
        "created_by",
    )
    list_filter = ("effective_to",)
    search_fields = ("show__title", "show__slug")
    readonly_fields = ("created_by",)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
