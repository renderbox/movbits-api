"""
Canonical event schemas for the Movbits analytics pipeline.

All events are plain dataclasses serialisable via dataclasses.asdict().
Every event includes:
  - event_type    : dotted string identifier e.g. "chapter.unlocked"
  - occurred_at   : ISO-8601 UTC timestamp string (auto-set on instantiation)
  - session_id    : opaque client-generated session identifier

Chapter / Video note:
  In the Movbits data model a "chapter" is a Video object. video_id holds the
  Video UUID, episode_id holds the Episode UUID, show_id holds the Show UUID.
"""

from __future__ import annotations

import dataclasses
from typing import Optional


def _now_iso() -> str:
    from django.utils import timezone

    return timezone.now().isoformat()


# ── Chapter / Playback ─────────────────────────────────────────────────────────


@dataclasses.dataclass
class ChapterUnlockedEvent:
    """
    Emitted when a VideoReceipt is created for a priced video.

    Rev share fields are snapshotted at transaction time so historical
    payouts can always be reconstructed regardless of later rate changes.
    """

    event_type: str = dataclasses.field(default="chapter.unlocked", init=False)
    occurred_at: str = dataclasses.field(default_factory=_now_iso)

    # Content identifiers
    video_id: str = ""  # Video.slug
    episode_id: str = ""  # Episode.slug
    show_id: str = ""  # Show.slug
    creator_team_id: str = ""  # Show.team UUID (str)

    # User
    user_id: str = ""
    session_id: str = ""

    # Transaction — credits are the unit; USD conversion happens downstream
    credits_spent: int = 0
    rev_share_rate: str = "0.70"  # Decimal snapshotted as string
    unlock_method: str = "credits"  # credits | ad | promotional | free

    # Request context (geo resolved downstream from ip_address)
    ip_address: str = ""
    user_agent: str = ""


@dataclasses.dataclass
class ChapterPlaybackEvent:
    """
    Emitted for chapter lifecycle transitions:
      chapter.started   — play begins
      chapter.paused    — user paused playback
      chapter.resumed   — user resumed from pause
      chapter.completed — playback position reached within 10 s of duration
      chapter.abandoned — player closed / navigated away before completion
      chapter.seeked    — user scrubbed the timeline
      chapter.stalled   — buffering / network stall
      chapter.replayed  — play triggered on an already-completed chapter
    """

    event_type: str = ""  # caller sets this to one of the values above
    occurred_at: str = dataclasses.field(default_factory=_now_iso)

    # Content identifiers
    video_id: str = ""
    episode_id: str = ""
    show_id: str = ""
    creator_team_id: str = ""

    # User
    user_id: str = ""
    session_id: str = ""

    # Playback state
    position_seconds: int = 0
    duration_seconds: int = 0  # full chapter duration; enables % calc downstream
    percent_complete: float = 0.0

    # chapter.seeked only
    seek_from_seconds: Optional[int] = None
    seek_to_seconds: Optional[int] = None

    # chapter.stalled only
    stall_duration_ms: Optional[int] = None

    # Request context
    ip_address: str = ""
    user_agent: str = ""
    device_type: str = ""  # mobile | desktop | tablet | tv (client-supplied)


# ── Purchases ─────────────────────────────────────────────────────────────────


@dataclasses.dataclass
class CreditPurchasedEvent:
    """
    Emitted after a Stripe payment_intent.succeeded webhook is processed and
    credits are applied to the user's wallet.

    Fired inside transaction.on_commit so the event is only emitted once the
    database write is durable.

    event_type: "purchase.credits_purchased"
    """

    event_type: str = dataclasses.field(
        default="purchase.credits_purchased", init=False
    )
    occurred_at: str = dataclasses.field(default_factory=_now_iso)

    # User / site
    user_id: str = ""
    site_id: str = ""
    stripe_customer_id: str = ""  # Stripe cus_xxx if available

    # Invoice / transaction identifiers
    invoice_id: str = ""  # vendor Invoice UUID
    stripe_payment_intent_id: str = ""  # pi_xxx
    stripe_event_id: str = ""  # evt_xxx (idempotency key)

    # Financials — minor units (e.g. cents for USD)
    amount_paid_minor: int = 0
    currency: str = "usd"

    # Credits
    credits_purchased: int = 0
    balance_after: int = 0


# ── App Errors ────────────────────────────────────────────────────────────────


@dataclasses.dataclass
class AppErrorEvent:
    """
    Emitted for each frontend error received by ErrorLogView.

    Mirrors the structured log entry already written to errors.log so that
    errors are queryable in BigQuery alongside other operational events.

    event_type: "app.error"
    """

    event_type: str = dataclasses.field(default="app.error", init=False)
    occurred_at: str = dataclasses.field(
        default_factory=_now_iso
    )  # client timestamp if available

    # Error identity
    error_id: str = ""  # server-assigned UUID, returned to the client
    batch_id: str = ""  # client batch grouping ID

    # Error detail
    message: str = ""
    stack: str = ""
    category: str = ""
    severity: str = "low"  # low | medium | high | critical

    # Client context
    url: str = ""
    user_agent: str = ""
    app_version: str = ""
    environment: str = ""

    # User context
    user_id: Optional[str] = None
    session_id: Optional[str] = None


# ── Referrals ─────────────────────────────────────────────────────────────────


@dataclasses.dataclass
class ReferralClickEvent:
    """
    Two event types share this schema:

    referral.clicked   — emitted on every link click (user may be anonymous).
    referral.attributed — emitted when a click is matched to a logged-in user
                          via the user_logged_in signal.

    anonymous_id is the stable join key between the two events and the
    bridge to chapter_unlocked for revenue attribution.

    Revenue attribution query (BigQuery):
      JOIN chapter_unlocked cu
        ON rc.user_id = cu.user_id
       AND cu.show_id = rc.show_id          -- scoped to referred show
       AND cu.occurred_at > rc.clicked_at
       AND TIMESTAMP_DIFF(cu.occurred_at, rc.clicked_at, DAY) <= 30
    """

    event_type: str = ""  # "referral.clicked" | "referral.attributed"
    occurred_at: str = dataclasses.field(default_factory=_now_iso)

    referral_click_id: str = ""  # ReferralClick PK (str)
    referral_link_id: str = ""  # ReferralLink PK (str)
    referral_slug: str = ""
    show_id: str = ""  # Show.uuid — revenue attribution anchor

    # anonymous_id bridges referral.clicked → referral.attributed
    anonymous_id: str = ""

    # Populated on referral.attributed only
    user_id: Optional[str] = None
    is_new_user: Optional[bool] = None

    ip_address: str = ""
    user_agent: str = ""


# ── Engagement (watchlist + ratings) ──────────────────────────────────────────


@dataclasses.dataclass
class WatchlistEvent:
    """
    Emitted when a user adds or removes a show from their watchlist.

    event_type: "watchlist.added" | "watchlist.removed"

    source identifies the UI surface where the action was triggered.
    Expected values (client-defined, not validated server-side):
      "show_page" | "search" | "discover" | "dashboard" | "home" | ""
    """

    event_type: str = ""  # caller sets "watchlist.added" or "watchlist.removed"
    occurred_at: str = dataclasses.field(default_factory=_now_iso)

    user_id: str = ""
    show_id: str = ""  # Show.uuid
    source: str = ""  # UI surface that triggered the action
    session_id: str = ""

    ip_address: str = ""
    user_agent: str = ""


@dataclasses.dataclass
class VideoRatingEvent:
    """
    Emitted when a user submits or changes their like/dislike on a video.

    rating values:
      0 = dislike
      1 = neutral (reaction removed)
      2 = like

    event_type: "video.rated"
    """

    event_type: str = dataclasses.field(default="video.rated", init=False)
    occurred_at: str = dataclasses.field(default_factory=_now_iso)

    user_id: str = ""
    video_id: str = ""  # Video.uuid
    episode_id: str = ""  # Episode.uuid
    show_id: str = ""  # Show.uuid

    rating: int = 1  # 0 | 1 | 2  (the new value)
    previous_rating: Optional[int] = (
        None  # None = first-time rating; 0|1|2 = changed from
    )
    session_id: str = ""

    ip_address: str = ""
    user_agent: str = ""


# ── Auth / Security ────────────────────────────────────────────────────────────


@dataclasses.dataclass
class AuthEvent:
    """
    Covers authentication and session lifecycle:
      auth.login_success | auth.login_failure | auth.logout |
      auth.token_refresh | auth.password_reset_requested |
      auth.password_reset_completed | auth.session_revoked
    """

    event_type: str = ""
    occurred_at: str = dataclasses.field(default_factory=_now_iso)

    user_id: Optional[str] = None
    email: Optional[str] = (
        None  # only on login events; cleared after anonymisation window
    )
    ip_address: str = ""
    user_agent: str = ""
    failure_reason: Optional[str] = None  # auth.login_failure only


# ── Admin / Audit ──────────────────────────────────────────────────────────────


@dataclasses.dataclass
class AdminAuditEvent:
    """
    Emitted for any privileged or destructive platform action:
      admin.user_suspended | admin.content_removed | admin.role_changed |
      admin.rev_share_deal_changed | admin.show_published | admin.show_unpublished
    """

    event_type: str = ""
    occurred_at: str = dataclasses.field(default_factory=_now_iso)

    actor_user_id: str = ""  # who performed the action
    target_type: str = ""  # e.g. "user", "show", "rev_share_deal"
    target_id: str = ""  # slug or UUID of the affected object
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    notes: str = ""
    ip_address: str = ""
