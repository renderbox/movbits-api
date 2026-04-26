import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.sites.models import Site
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils.text import slugify

from team.models import Team


class BaseModel(models.Model):
    """sets up time stamp attributes for models"""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class TitledModel(BaseModel):
    """adds title, slug, images, tags, and uuid to models"""

    title = models.CharField(max_length=255)
    slug = models.SlugField(editable=False)
    description = models.TextField(blank=True, null=True)
    tags = models.ManyToManyField("Tag", blank=True)
    poster_file = models.ImageField(
        blank=True,
        null=True,
        help_text="the original poster image file, others are derrived",
    )
    poster_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to the poster image, derrived from the file upload",
    )
    banner_file = models.ImageField(
        blank=True,
        null=True,
        help_text="the original banner image file, others are derrived",
    )
    banner_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to the banner image, derrived from the file upload",
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        base_slug = slugify(self.title) or uuid.uuid4().hex
        slug_candidate = base_slug
        counter = 1
        qs = self.__class__.objects
        while qs.filter(slug=slug_candidate).exclude(pk=self.pk).exists():
            slug_candidate = f"{base_slug}-{counter}"
            counter += 1
        self.slug = slug_candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Tag(models.Model):
    """Tags for categorizing shows"""

    class TagType(models.IntegerChoices):
        GENERAL = 1, "General"
        GENRE = 2, "Genre"
        CALL_OUT = 3, "Call-Out"

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    tagtype = models.IntegerField(choices=TagType.choices, default=TagType.GENERAL)
    # include language code?

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug or self.name:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# Show
class Show(TitledModel):
    """The top level of each show"""

    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="shows")
    series = models.BooleanField(
        default=False,
        help_text="Indicates if the show is a series with multiple episodes",
    )

    rating_value = models.IntegerField(
        help_text="Average user rating from 0 to 50, converted to 0.0 to 5.0",
        blank=True,
        null=True,
    )
    rating_count = models.IntegerField(
        help_text="Number of user ratings for this show", default=0
    )


class Season(TitledModel):
    """To help organize shows into seasons if needed.  This lets each season have it's own title and poster."""

    order = models.IntegerField(default=1)
    show = models.ForeignKey(Show, on_delete=models.CASCADE)


# Episode with the Playlist
class Episode(TitledModel):
    """The show's content list"""

    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    order = models.IntegerField(default=1, help_text="Order within the show's season")
    season = models.ForeignKey(
        Season,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Optional Item for a Show with seasons.",
    )
    playlist = models.ManyToManyField("Video", through="EpisodeVideo")
    duration = models.IntegerField(
        help_text="Duration in seconds based on sum of videos attached", default=0
    )
    rating_value = models.IntegerField(
        help_text="Average user rating from 0 to 50, converted to 0.0 to 5.0",
        blank=True,
        null=True,
    )
    rating_count = models.IntegerField(
        help_text="Number of user ratings for this episode", default=0
    )
    chapter_count = models.IntegerField(
        help_text="Number of videos/chapters in this episode", default=0
    )

    # on save, update the chapter_count with active videos in the playlist
    def save(self, *args, **kwargs):
        if self.pk:
            self.chapter_count = self.playlist.count()
        super().save(*args, **kwargs)


class VideoRating(models.Model):
    """
    Per-user reaction on a Video (chapter).

    rating:
      0 = dislike
      1 = neutral / no reaction (default — effectively means "remove rating")
      2 = like

    rating_value and rating_count on Video are kept in sync synchronously
    on every save, excluding neutral (1) ratings from the aggregate.
    """

    class Rating(models.IntegerChoices):
        DISLIKE = 0, "Dislike"
        NEUTRAL = 1, "Neutral"
        LIKE = 2, "Like"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="video_ratings",
    )
    video = models.ForeignKey(
        "Video",
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    rating = models.IntegerField(choices=Rating.choices, default=Rating.NEUTRAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "video")

    def __str__(self):
        return f"{self.user} → {self.video} = {self.rating}"


class EpisodeVideo(BaseModel):
    """A many-to-many relationship between Episode and Video, with an order field to sort the playlist"""

    playlist = models.ForeignKey(Episode, on_delete=models.CASCADE)
    video = models.ForeignKey("Video", on_delete=models.CASCADE)
    order = models.IntegerField(default=1)

    # always sort by order
    class Meta:
        ordering = ["order"]
        # TODO: add a unique constraint on playlist and video


@receiver(m2m_changed, sender=Episode.playlist.through)
def update_episode_chapter_count(sender, instance, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        count = instance.playlist.count()
        Episode.objects.filter(pk=instance.pk).update(chapter_count=count)
        instance.chapter_count = count


# Videos (aka, each chapter)
class Video(TitledModel):
    """
    eample path:
    video/uuid/encodes/v2/hls/720p/segment_014.ts

    video/<uuid>/
    src/
        original.mov
        v2_original.mov   ← optional future
    encodes/
        v1/
            hls/
                master.m3u8
                1080p/
                720p/
                480p/
            mp4/
                1080p.mp4
                720p.mp4
        v2/
            ...
    assets/
        thumbnails/
        posters/
        preview_clips/
    captions/
        en.vtt
        es.vtt
    metadata.json
    """

    class CDNChoices(models.IntegerChoices):
        VIMEO = 1, "Vimeo"
        YOUTUBE = 2, "YouTube"
        S3_MEDIA_BUCKET = 3, "Amazon S3 Bucket"

    # Video details
    video_key = models.CharField(
        blank=True, null=True, help_text="The key or ID for the video in the CDN"
    )
    cdn = models.IntegerField(choices=CDNChoices.choices)
    meta = models.JSONField(
        blank=True,
        null=True,
        help_text="Optional JSON field to store meta data like clip information for the HLS playlist.",
    )
    price = models.IntegerField(default=0)  # in credits
    duration = models.IntegerField(help_text="Duration in seconds", default=0)
    rating_value = models.IntegerField(
        help_text="Average user rating from 0 to 50, converted to 0.0 to 5.0",
        blank=True,
        null=True,
    )
    rating_count = models.IntegerField(
        help_text="Number of user ratings for this episode", default=0
    )
    version = models.IntegerField(
        default=1,
        help_text="Version of the video, used for updating the video and generating new signed URLs",
    )

    def get_video_url(self):
        """Return the full URL to the video based on the CDN and video_key."""
        if not self.video_key:
            return None
        if self.cdn == self.CDNChoices.VIMEO:
            return f"https://vimeo.com/{self.video_key}"
        elif self.cdn == self.CDNChoices.YOUTUBE:
            return f"https://www.youtube.com/watch?v={self.video_key}"
        elif self.cdn == self.CDNChoices.S3_MEDIA_BUCKET:
            # return reverse(
            #     "hls_playlist",
            #     kwargs={"video_id": self.uuid, "playlist_id": "playlist"},
            # )
            return self.get_cloudfront_playlist_url()
        return None

    def get_cloudfront_playlist_url(self):
        """Return the CloudFront URL for the video based on the CDN and video_key."""
        if not self.video_key:
            return None
        if self.cdn == self.CDNChoices.S3_MEDIA_BUCKET:
            return f"https://{settings.CLOUDFRONT_DOMAIN}/videos/{self.uuid}/hls/master.m3u8"
        return None

    def get_video_bucket_path(self):
        return f"videos/{self.uuid}/"

    def get_video_source_path(self):
        return f"{self.get_video_bucket_path()}src/"

    def get_video_assets_path(self):
        return f"{self.get_video_bucket_path()}assets/"

    def get_video_thumbnails_path(self):
        return f"{self.get_video_assets_path()}thumbnails/"

    def get_video_posters_path(self):
        return f"{self.get_video_assets_path()}posters/"

    def get_video_hls_path(self, version=None):
        return f"{self.get_video_bucket_path()}encodes/v{version}/hls/"

    def get_video_mp4_path(self, version=None):
        return f"{self.get_video_bucket_path()}encodes/v{version}/mp4/"

    def get_video_captions_path(self):
        return f"{self.get_video_bucket_path()}captions/"


class Watchlist(BaseModel):
    """Tracks shows a user has saved to their watchlist."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist",
    )
    show = models.ForeignKey(
        Show,
        on_delete=models.CASCADE,
        related_name="watchlisted_by",
    )

    class Meta:
        unique_together = ("user", "show")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} → {self.show}"


class VideoReceipt(models.Model):
    """Tracks user purchases of videos.  Not required if the video is free (aka, price is 0)."""

    user = models.ForeignKey(
        "core.StoryUser", on_delete=models.CASCADE, related_name="video_receipts"
    )
    episode = models.ForeignKey(
        Episode,
        on_delete=models.CASCADE,
        help_text="The episode this receipt is attached to",
    )
    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name="receipts",
        help_text="The specific video this receipt is for",
    )
    purchased_at = models.DateTimeField(auto_now_add=True)
    watch_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "When the user first pressed play. NULL means purchased but not yet watched. "
            "The access window (expiration_date) is set from this timestamp."
        ),
    )
    expiration_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Access expires at this time. NULL means the watch window has not started yet "
            "(purchased but unwatched). Set to watch_started_at + VIDEO_ACCESS_WINDOW_HOURS "
            "on first play."
        ),
    )

    def __str__(self):
        return (
            f"Receipt for {self.user.email} - {self.video.title} at {self.purchased_at}"
        )


class RevShareDeal(models.Model):
    """
    Tracks the revenue-share rate for a Show.

    A new record is inserted whenever the rate changes; the *current* deal is
    the one where effective_to is NULL.  The previous record's effective_to is
    set to the new record's effective_from so the full history is queryable.

    The platform default is 70 % to the creator (creator_rate = 0.70).
    """

    DEFAULT_CREATOR_RATE = Decimal("0.70")

    show = models.ForeignKey(
        Show,
        on_delete=models.CASCADE,
        related_name="rev_share_deals",
    )
    creator_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=DEFAULT_CREATOR_RATE,
        help_text="Fraction of gross revenue paid to the creator (0.70 = 70 %).",
    )
    effective_from = models.DateTimeField(
        help_text="When this rate came into effect.",
    )
    effective_to = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this rate ended. NULL means this is the currently active deal.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Platform user who created or approved this deal.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self) -> str:
        to = self.effective_to.date() if self.effective_to else "present"
        pct = self.creator_rate * 100
        return f"{self.show} — {pct:.0f}% from {self.effective_from.date()} to {to}"

    @classmethod
    def current_rate_for_show(cls, show: "Show") -> Decimal:
        """
        Return the creator's current rev-share rate for *show*.
        Falls back to DEFAULT_CREATOR_RATE if no deal record exists.
        """
        deal = cls.objects.filter(show=show, effective_to__isnull=True).first()
        return deal.creator_rate if deal else cls.DEFAULT_CREATOR_RATE
