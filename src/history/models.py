from django.conf import settings
from django.db import models
from django.utils import timezone

from shows.models import Episode


class ViewingHistory(models.Model):
    """
    Tracks a user's progress watching an Episode.

    One record per user/episode pair — updated in place as the user watches.
    `progress` is an integer 0–100 representing percentage watched.
    `watched_at` is updated every time progress is recorded, so it always
    reflects the most recent watch activity.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="viewing_history",
    )
    episode = models.ForeignKey(
        Episode,
        on_delete=models.CASCADE,
        related_name="viewing_history",
    )
    last_video_index = models.PositiveSmallIntegerField(
        default=0,
        help_text=(
            "1-based index of the last completed video in the episode playlist. "
            "0 means no videos completed yet — start from chapter 1. "
            "If last_video_index == chapter_count, the episode is fully watched."
        ),
    )
    last_video_position = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Playback position in seconds within the current chapter "
            "(last_video_index + 1). Updated as the user watches. "
            "Reset to 0 when they move to the next chapter."
        ),
    )
    progress = models.PositiveSmallIntegerField(
        default=0,
        help_text=(
            "Percentage watched, 0–100. Derived from last_video_index / chapter_count "
            "but stored for fast reads."
        ),
    )
    watched_at = models.DateTimeField(
        default=timezone.now,
        help_text="Most recent time the user watched this episode.",
    )

    class Meta:
        unique_together = ("user", "episode")
        ordering = ["-watched_at"]

    def __str__(self):
        return f"{self.user.email} → {self.episode} ({self.progress}%)"
