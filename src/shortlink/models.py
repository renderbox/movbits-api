import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from shows.models import Show


class ReferralLink(models.Model):
    LINK_TYPE_CHOICES = [
        ("unique", "Unique"),
        ("shared", "Shared"),
    ]

    show = models.ForeignKey(
        Show, on_delete=models.CASCADE, related_name="referral_links"
    )
    slug = models.SlugField(unique=True, max_length=255)
    name = models.CharField(
        max_length=255, help_text="Custom name for the referral link"
    )
    description = models.CharField(max_length=500, blank=True)
    cta_text = models.CharField(max_length=100, default="Learn More")
    link_type = models.CharField(
        max_length=10, choices=LINK_TYPE_CHOICES, default="shared"
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    click_count = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)
    assigned_email = models.EmailField(blank=True)
    deleted = models.BooleanField(
        default=False, help_text="Indicates if the referral link is soft deleted"
    )

    def __str__(self):
        return f"Referral for {self.show.title} — {self.name}"

    def get_absolute_url(self):
        return reverse("shortlink:referral", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        if self.slug and " " in self.slug:
            self.slug = slugify(self.slug)
        elif not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.deleted = True
        self.save()


class ReferralClick(models.Model):
    """
    One record per referral link click.

    Replaces the coarse click_count integer on ReferralLink with individual
    click records that support anonymous-to-user attribution and revenue
    analysis scoped to the referred show.

    Attribution flow
    ----------------
    1. Visitor hits the referral link → ReferralClick created with anonymous_id
       from the mvb_anon_id cookie (90-day lifetime).  user is NULL.
    2. Visitor logs in (new signup or returning user) → user_logged_in signal
       fires, finds the most recent unattributed click for that anonymous_id,
       and sets user, attributed_at, and is_new_user.
    3. BigQuery joins ReferralClick.user_id → chapter_unlocked.user_id
       filtered to chapter_unlocked.show_id == ReferralClick.show_id
       within a 30-day window to measure revenue driven by the referral.
    """

    ANON_COOKIE = "mvb_anon_id"
    ANON_COOKIE_MAX_AGE = 60 * 60 * 24 * 90  # 90 days in seconds

    referral_link = models.ForeignKey(
        ReferralLink,
        on_delete=models.CASCADE,
        related_name="clicks",
    )
    # Stable anonymous identity written into a 90-day cookie on first click.
    # Used to bridge the gap between click and login attribution.
    anonymous_id = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        help_text="UUID from the mvb_anon_id cookie. Persists across login.",
    )
    session_key = models.CharField(
        max_length=40,
        blank=True,
        help_text="Django session key at click time — secondary correlation.",
    )

    # Filled in by the user_logged_in signal (last-touch, 30-day window).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referral_clicks",
    )
    is_new_user = models.BooleanField(
        null=True,
        blank=True,
        help_text="True if the attributed user registered after this click.",
    )
    attributed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the click was matched to a logged-in user.",
    )

    clicked_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-clicked_at"]

    def __str__(self):
        return (
            f"Click on {self.referral_link.slug} "
            f"by {'user ' + str(self.user_id) if self.user_id else 'anon ' + str(self.anonymous_id)}"
        )
