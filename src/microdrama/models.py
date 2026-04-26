import datetime
import os
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify

from team.models import Team



s3_video_bucket_url = "https://movbits-media.s3.us-east-1.amazonaws.com"


def series_poster_upload_path(instance, filename):
    base_filename, file_extension = os.path.splitext(filename)
    title_slug = slugify(instance.title)
    filename_slug = slugify(base_filename.lower())

    return f"posters/{title_slug}/{filename_slug}{file_extension.lower()}"


def chapter_video_upload_path(instance, filename):
    """
    Returns the upload path for chapter videos.
    Uses the chapter UUID to create a unique directory.
    """
    base_filename, file_extension = os.path.splitext(filename)
    return f"ch/{instance.uuid}/video/src/{base_filename}{file_extension}"


# def chapter_video_hls_path(instance, filename):
#     """
#     Returns the upload path for chapter videos.
#     Uses the chapter UUID to create a unique directory.
#     """
#     base_filename, file_extension = os.path.splitext(filename)
#     return f"ch/{instance.uuid}/video/hls/{base_filename}{file_extension}"


class TimeStampModel(models.Model):
    """Abstract model to add created_at and updated_at fields"""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Series(TimeStampModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField()
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="microdramas")
    min_age = models.IntegerField(
        default=0, help_text="Minimum age to watch the series"
    )
    poster = models.ImageField(
        upload_to=series_poster_upload_path, null=True, blank=True
    )
    sites = models.ManyToManyField(
        Site,
        blank=True,
        help_text="Select which sites this series is available on",
        related_name="microdrama_series",
        # related_query_name defaults to the model name if you omit it,
        # but because we’ve set related_name we’ll leave related_query_name alone.
    )
    active = models.BooleanField(default=True, help_text="Is this series active?")
    episode_count = models.IntegerField(
        default=0, help_text="Number of active episodes"
    )

    class Meta:
        verbose_name = "Series"
        verbose_name_plural = "Series"
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """
        Returns the URL to the SeriesDetail view:
        /<team-slug>/<series-slug>/
        """
        return reverse(
            "series-detail",
            kwargs={
                "team": self.team.slug,
                "series": self.slug,
            },
        )

    def get_series_key(self):
        """
        Returns the URL to the SeriesDetail view:
        /<team-slug>/<series-slug>/
        """
        return f"{self.team.slug}/{self.slug}"


class SeriesStats(models.Model):
    """
    Model to track the statistics of a series, per site.
    """

    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name="stats")
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        help_text="Select which site these stats apply to",
        related_name="microdrama_series_stats",
        related_query_name="series_stats",
    )
    views = models.IntegerField(default=0)
    likes = models.IntegerField(default=0)
    dislikes = models.IntegerField(default=0)

    class Meta:
        unique_together = ("series", "site")
        verbose_name = "Series Stats"
        verbose_name_plural = "Series Stats"

    def __str__(self):
        return f"Stats for {self.series.title} ({self.site.domain})"


def episode_data_default():
    """
    Default data for the episode. This is a JSON object with the following structure:
    {
        "free_chapters": [1, 2, 3]
    }
    """
    return {"free_chapters": []}


class Episode(TimeStampModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(
        max_length=255
    )  # Removed unique=True as uniqueness is enforced by unique_together
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    description = models.TextField(blank=True, null=True)
    series = models.ForeignKey(
        Series, on_delete=models.CASCADE, related_name="episodes"
    )
    price = models.IntegerField(default=10)  # Price in tokens for each chapter
    data = models.JSONField(default=episode_data_default, blank=True, null=True)
    order = models.IntegerField(default=0, help_text="Episode number in the series")
    active = models.BooleanField(default=True, help_text="Is this episode active?")
    chapter_count = models.IntegerField(
        default=0, help_text="Number of active chapters"
    )

    class Meta:
        unique_together = ("series", "slug")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """
        Returns the URL to play this episode:
        /<team-slug>/<series-slug>/<episode-slug>/player/
        """
        return reverse(
            "player",
            kwargs={
                "team": self.series.team.slug,
                "series": self.series.slug,
                "episode": self.slug,
            },
        )


class Chapter(TimeStampModel):
    class CDNChoices(models.IntegerChoices):
        VIMEO = 1, "Vimeo"
        YOUTUBE = 2, "YouTube"
        S3_MEDIA_BUCKET = 3, "Amazon S3 Media Bucket"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=255)
    episode = models.ForeignKey(
        Episode, on_delete=models.CASCADE, related_name="chapters"
    )
    # The number of the chapter in the episode starting at 0
    chapter_number = models.IntegerField(help_text="Chapter number in the episode")
    # The String ID of the video in the Content Delivery Network (CDN)
    video_url = models.CharField(blank=True, null=True)  # Made video_url optional
    cdn = models.IntegerField(choices=CDNChoices.choices)
    active = models.BooleanField(default=True, help_text="Is this chapter active?")
    free = models.BooleanField(
        default=False, help_text="Is this chapter free to watch?"
    )
    transcoded = models.BooleanField(
        default=False, help_text="Has the video been transcoded and is ready to watch?"
    )  # should be set to False when a new video is uploaded
    src_video = models.FileField(
        upload_to=chapter_video_upload_path,
        blank=True,
        null=True,
        help_text="Source video file for transcoding",
    )
    playlist_text = models.TextField(
        blank=True, null=True, help_text="Raw HLS playlist content"
    )

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.episode.get_absolute_url() + f"{self.chapter_number}/"

    def get_video_url(self):
        """
        Returns the URL to play this chapter's video.
        This can be overridden in subclasses for different CDNs.
        """
        if self.cdn == self.CDNChoices.VIMEO:
            return f"https://vimeo.com/{self.video_url}"
        elif self.cdn == self.CDNChoices.YOUTUBE:
            return f"https://youtube.com/watch?v={self.video_url}"
        elif self.cdn == self.CDNChoices.S3_MEDIA_BUCKET:
            return reverse(
                "signed_playlist",
                kwargs={"uuid": self.uuid, "filename": self.video_url},
            )
        return None

    def get_hls_dir(self):
        """
        Returns the directory where HLS files are stored for this chapter.
        This is used to generate the signed playlist URL.
        """
        return f"ch/{self.uuid}/video/hls/"


class LibraryEntry(models.Model):  # TODO: rename to UserLibraryEntry?
    """
    Model to track a user's overall progression for an episode.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="progressions"
    )
    episode = models.ForeignKey(
        Episode, on_delete=models.CASCADE, related_name="progressions"
    )
    referral_id = models.IntegerField(
        null=True, blank=True, help_text="Referral ID associated with this entry"
    )

    class Meta:
        unique_together = ("user", "episode")
        verbose_name = "Library Entry"
        verbose_name_plural = "Library Entries"

    def __str__(self):
        return f"{self.user} - {self.episode}"


class ChapterView(models.Model):
    # TODO: rename to ChapterProgression since View is misleading
    """
    Tracks a user's progress for a specific chapter in an episode, attached to a LibraryEntry.
    """

    class ChapterState(models.IntegerChoices):
        LOCKED = 0, "Locked (not watched)"
        FREE_UNWATCHED = 1, "Free and unwatched"
        FREE_WATCHED = 2, "Free and watched"
        PAID_UNWATCHED = 3, "Paid and unwatched"
        PAID_WATCHED = 4, "Paid and watched"
        IN_PROGRESS = 5, "In progress"

    library = models.ForeignKey(
        LibraryEntry, on_delete=models.CASCADE, related_name="chapter_views"
    )
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="views")
    state = models.IntegerField(
        choices=ChapterState.choices, default=ChapterState.LOCKED
    )
    unlocked_at = models.DateTimeField(null=True, blank=True)
    watched_at = models.DateTimeField(null=True, blank=True)
    price = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("library", "chapter")
        verbose_name = "Chapter View"
        verbose_name_plural = "Chapter Views"

    def __str__(self):
        return f"{self.library} - {self.chapter} ({self.get_state_display()})"

    def save(self, *args, **kwargs):
        # Set unlocked_at if this is a new object and the chapter is free
        if self._state.adding and self.chapter.free and not self.unlocked_at:
            self.unlocked_at = datetime.datetime.now()
            self.price = 0
            self.state = self.ChapterState.FREE_UNWATCHED
        super().save(*args, **kwargs)


class SeriesMarketing(models.Model):
    class Placement(models.IntegerChoices):
        HIDDEN_GEMS = 1, "Hidden Gems"
        HERO = 2, "Hero Section"
        MUST_SEE = 3, "Must See"
        TRENDING = 4, "Trending"
        # Add more placements as needed

    series = models.ForeignKey(
        Series, on_delete=models.CASCADE, related_name="marketing"
    )
    placement = models.IntegerField(choices=Placement.choices)
    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name="series_marketing"
    )
    order = models.IntegerField(
        default=0, help_text="Order for display (lower comes first)"
    )

    class Meta:
        unique_together = ("site", "placement", "order")
        verbose_name = "Series Marketing"
        verbose_name_plural = "Series Marketing"

    def __str__(self):
        return (
            f"{self.series.title} - {self.get_placement_display()} ({self.site.domain})"
        )


@receiver([post_save, post_delete], sender=Episode)
def update_series_episode_count(sender, instance, **kwargs):
    series = instance.series
    count = series.episodes.filter(active=True).count()
    if series.episode_count != count:
        series.episode_count = count
        series.save(update_fields=["episode_count"])


@receiver([post_save, post_delete], sender=Chapter)
def update_episode_chapter_count(sender, instance, **kwargs):
    episode = instance.episode
    count = episode.chapters.filter(active=True).count()
    if episode.chapter_count != count:
        episode.chapter_count = count
        episode.save(update_fields=["chapter_count"])


def library_data_default():
    pass


# REWORK LATER

# class CDNChoices(models.IntegerChoices):
#     VIMEO = 1, "Vimeo"
#     YOUTUBE = 2, "YouTube"
#     S3_MEDIA_BUCKET = 3, "Amazon S3 Media Bucket"


# class Video(TimeStampModel):

#     uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
#     active = models.BooleanField(default=True)
#     name = models.CharField(max_length=255)
#     transcoded = models.BooleanField(
#         default=False, help_text="Has the video been transcoded and is ready to watch?"
#     )  # should be set to False when a new video is uploaded
#     src_video = models.FileField(
#         upload_to=chapter_video_upload_path,
#         blank=True,
#         null=True,
#         help_text="Source video file for transcoding",
#     )
#     poster = models.ImageField(
#         upload_to="video_posters/", blank=True, null=True, help_text="Poster image"
#     )
#     cdn = models.IntegerField(choices=CDNChoices.choices, default=3)
#     video_id = models.CharField(
#         max_length=255,
#         blank=True,
#         null=True,
#         help_text="The ID of the video in the CDN (e.g., Vimeo ID or YouTube ID.  S3 used uuid as key)",
#     )

#     def get_video_url(self):
#         """
#         Returns the URL to play this chapter's video.
#         This can be overridden in subclasses for different CDNs.
#         """
#         if self.cdn == self.CDNChoices.VIMEO:
#             return f"https://vimeo.com/{self.video_url}"
#         elif self.cdn == self.CDNChoices.YOUTUBE:
#             return f"https://youtube.com/watch?v={self.video_url}"
#         elif self.cdn == self.CDNChoices.S3_MEDIA_BUCKET:
#             return reverse(
#                 "signed_playlist",
#                 kwargs={"uuid": self.uuid, "filename": self.video_url},
#             )
#         return None


class Collection(TimeStampModel):
    """
    Model to represent a collection of Playlists.

    Example: A "Season 1" collection that contains multiple playlists (episodes).
    """

    class ChapterState(models.IntegerChoices):
        EPISODIC = 0, "Locked (not watched)"
        FREE_UNWATCHED = 1, "Free and unwatched"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255)
    ctype = models.IntegerField()


class Playlist(TimeStampModel):
    """
    Model to represent a playlist of videos.  These playlists can be tied to episodes and represent Chapters.
    """

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255)

    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        related_name="playlists",
        blank=True,
        null=True,
    )


class Video(TimeStampModel):
    """
    Model to represent a video in a playlist.
    """

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    playlist = models.ForeignKey(
        Playlist, on_delete=models.CASCADE, related_name="videos", blank=True, null=True
    )
    order = models.IntegerField(default=0, help_text="Order in the playlist")
