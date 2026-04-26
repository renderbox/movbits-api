"""
Public interface for emitting analytics events.

Failures are swallowed and logged — event emission must never break the
request/response cycle.

Usage:
    from events.emit import emit, TOPIC_ANALYTICS, TOPIC_REVENUE, TOPIC_AUDIT
    from events.schemas import ChapterUnlockedEvent

    emit(TOPIC_REVENUE, ChapterUnlockedEvent(video_id=str(video.uuid), ...))
"""

import dataclasses
import logging

from .pubsub import get_publisher

logger = logging.getLogger("events.emit")

# Topic names — match the Pub/Sub topic names created in GCP.
# Override via settings.PUBSUB_TOPIC_ANALYTICS etc. if environment-specific
# naming is needed (e.g. "movbits-analytics-prod").
TOPIC_ANALYTICS = "analytics"  # playback, engagement, discovery
TOPIC_REVENUE = "revenue"  # chapter unlocks with rev share snapshots
TOPIC_PURCHASES = "purchases"  # credit package purchases via Stripe
TOPIC_REFERRALS = "referrals"  # referral link clicks and attribution
TOPIC_ERRORS = "errors"  # frontend app errors
TOPIC_AUDIT = "audit"  # auth, admin actions, access violations
TOPIC_ENGAGEMENT = "engagement"  # watchlist add/remove, video ratings


def _topic_name(base: str) -> str:
    """Allow per-environment topic name overrides via Django settings."""
    from django.conf import settings

    overrides = getattr(settings, "PUBSUB_TOPIC_OVERRIDES", {})
    return overrides.get(base, base)


def emit(topic: str, event: object) -> None:
    """
    Serialise *event* (a dataclass instance) and publish to *topic*.

    Any exception during serialisation or publishing is caught, logged,
    and silently discarded so callers are never disrupted.
    """
    try:
        payload = dataclasses.asdict(event)  # type: ignore[call-overload]
        get_publisher().publish(_topic_name(topic), payload)
    except Exception:
        logger.exception(
            "Failed to emit event %s to topic %s",
            getattr(event, "event_type", "unknown"),
            topic,
        )
