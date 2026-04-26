"""
Tests for the events emit infrastructure.
"""

import dataclasses
from unittest.mock import MagicMock, patch

import pytest

from events.emit import (
    TOPIC_ANALYTICS,
    TOPIC_AUDIT,
    TOPIC_ENGAGEMENT,
    TOPIC_REVENUE,
    emit,
)
from events.pubsub import LoggingPublisher, reset_publisher
from events.schemas import (
    AdminAuditEvent,
    ChapterPlaybackEvent,
    ChapterUnlockedEvent,
    ReferralClickEvent,
    VideoRatingEvent,
    WatchlistEvent,
)


@pytest.fixture(autouse=True)
def reset_publisher_singleton():
    """Ensure each test starts with a fresh publisher singleton."""
    reset_publisher()
    yield
    reset_publisher()


# ── LoggingPublisher ───────────────────────────────────────────────────────────


class TestLoggingPublisher:
    def test_publish_does_not_raise(self):
        pub = LoggingPublisher()
        pub.publish("analytics", {"event_type": "chapter.started"})

    def test_publish_logs_at_info(self):
        pub = LoggingPublisher()
        with patch("events.pubsub.logger") as mock_logger:
            pub.publish(
                "analytics", {"event_type": "chapter.started", "video_id": "ep1-ch1"}
            )
        mock_logger.info.assert_called_once()
        call_str = str(mock_logger.info.call_args)
        assert "chapter.started" in call_str
        assert "analytics" in call_str


# ── emit() ─────────────────────────────────────────────────────────────────────


class TestEmit:
    def test_emit_calls_publisher(self):
        mock_pub = MagicMock()
        with patch("events.emit.get_publisher", return_value=mock_pub):
            event = ChapterUnlockedEvent(video_id="vid-1", credits_spent=5)
            emit(TOPIC_REVENUE, event)

        mock_pub.publish.assert_called_once()
        topic_arg, payload_arg = mock_pub.publish.call_args[0]
        assert topic_arg == TOPIC_REVENUE
        assert payload_arg["event_type"] == "chapter.unlocked"
        assert payload_arg["video_id"] == "vid-1"
        assert payload_arg["credits_spent"] == 5

    def test_emit_swallows_publisher_exception(self):
        mock_pub = MagicMock()
        mock_pub.publish.side_effect = RuntimeError("pubsub down")
        with patch("events.emit.get_publisher", return_value=mock_pub):
            # Must not raise
            emit(TOPIC_ANALYTICS, ChapterPlaybackEvent(event_type="chapter.started"))

    def test_emit_respects_topic_override(self, settings):
        settings.PUBSUB_TOPIC_OVERRIDES = {"revenue": "movbits-revenue-prod"}
        mock_pub = MagicMock()
        with patch("events.emit.get_publisher", return_value=mock_pub):
            emit(TOPIC_REVENUE, ChapterUnlockedEvent())
        topic_arg = mock_pub.publish.call_args[0][0]
        assert topic_arg == "movbits-revenue-prod"


# ── ChapterUnlockedEvent schema ────────────────────────────────────────────────


class TestChapterUnlockedEvent:
    def test_event_type_is_fixed(self):
        event = ChapterUnlockedEvent()
        assert event.event_type == "chapter.unlocked"

    def test_occurred_at_is_populated(self):
        event = ChapterUnlockedEvent()
        assert event.occurred_at  # non-empty string

    def test_rev_share_rate_default(self):
        event = ChapterUnlockedEvent()
        assert event.rev_share_rate == "0.70"

    def test_serialises_to_dict(self):
        event = ChapterUnlockedEvent(
            video_id="v1",
            episode_id="ep1",
            show_id="show1",
            creator_team_id="team-uuid",
            user_id="user-uuid",
            credits_spent=10,
            rev_share_rate="0.80",
        )
        d = dataclasses.asdict(event)
        assert d["event_type"] == "chapter.unlocked"
        assert d["credits_spent"] == 10
        assert d["rev_share_rate"] == "0.80"


# ── ChapterPlaybackEvent schema ────────────────────────────────────────────────


class TestChapterPlaybackEvent:
    def test_seek_fields_default_to_none(self):
        event = ChapterPlaybackEvent(event_type="chapter.started")
        assert event.seek_from_seconds is None
        assert event.seek_to_seconds is None
        assert event.stall_duration_ms is None

    def test_percent_complete_stored(self):
        event = ChapterPlaybackEvent(
            event_type="chapter.completed",
            position_seconds=118,
            duration_seconds=120,
            percent_complete=98.3,
        )
        d = dataclasses.asdict(event)
        assert d["percent_complete"] == 98.3


# ── VideoRatingEvent schema ────────────────────────────────────────────────────


class TestVideoRatingEvent:
    def test_event_type_is_fixed(self):
        event = VideoRatingEvent()
        assert event.event_type == "video.rated"

    def test_previous_rating_defaults_to_none(self):
        # None means this is the user's first rating on the video.
        event = VideoRatingEvent(rating=2)
        assert event.previous_rating is None

    def test_previous_rating_records_old_value(self):
        event = VideoRatingEvent(rating=0, previous_rating=2)
        assert event.previous_rating == 2

    def test_previous_rating_included_in_serialisation(self):
        event = VideoRatingEvent(
            user_id="u1",
            video_id="vid-uuid",
            episode_id="ep-uuid",
            show_id="show-uuid",
            rating=2,
            previous_rating=None,
        )
        d = dataclasses.asdict(event)
        assert d["rating"] == 2
        assert d["previous_rating"] is None
        assert d["video_id"] == "vid-uuid"

    def test_ids_are_uuids_not_slugs(self):
        # Confirm the schema documents UUIDs (enforced by convention, not type).
        # At minimum the fields accept UUID strings without error.
        import uuid

        event = VideoRatingEvent(
            video_id=str(uuid.uuid4()),
            episode_id=str(uuid.uuid4()),
            show_id=str(uuid.uuid4()),
        )
        d = dataclasses.asdict(event)
        assert len(d["video_id"]) == 36  # standard UUID string length


# ── WatchlistEvent schema ──────────────────────────────────────────────────────


class TestWatchlistEvent:
    def test_source_defaults_to_empty_string(self):
        event = WatchlistEvent(event_type="watchlist.added", show_id="show-uuid")
        assert event.source == ""

    def test_source_captured_when_provided(self):
        event = WatchlistEvent(
            event_type="watchlist.added",
            show_id="show-uuid",
            source="show_page",
        )
        assert event.source == "show_page"

    def test_both_event_types_serialise(self):
        for et in ("watchlist.added", "watchlist.removed"):
            event = WatchlistEvent(event_type=et, show_id="s", source="discover")
            d = dataclasses.asdict(event)
            assert d["event_type"] == et
            assert d["source"] == "discover"

    def test_show_id_is_uuid_field(self):
        import uuid

        uid = str(uuid.uuid4())
        event = WatchlistEvent(event_type="watchlist.added", show_id=uid)
        assert dataclasses.asdict(event)["show_id"] == uid

    def test_emits_to_engagement_topic(self):
        mock_pub = MagicMock()
        with patch("events.emit.get_publisher", return_value=mock_pub):
            emit(
                TOPIC_ENGAGEMENT,
                WatchlistEvent(event_type="watchlist.added", show_id="x"),
            )
        topic_arg = mock_pub.publish.call_args[0][0]
        assert topic_arg == TOPIC_ENGAGEMENT


# ── ReferralClickEvent schema ──────────────────────────────────────────────────


class TestReferralClickEvent:
    def test_show_id_accepts_uuid_string(self):
        import uuid

        uid = str(uuid.uuid4())
        event = ReferralClickEvent(
            event_type="referral.clicked",
            show_id=uid,
            anonymous_id=str(uuid.uuid4()),
        )
        d = dataclasses.asdict(event)
        assert d["show_id"] == uid

    def test_user_id_none_for_anonymous(self):
        event = ReferralClickEvent(event_type="referral.clicked")
        assert event.user_id is None

    def test_attributed_event_has_user_id_and_is_new_user(self):
        event = ReferralClickEvent(
            event_type="referral.attributed",
            user_id="42",
            is_new_user=True,
        )
        d = dataclasses.asdict(event)
        assert d["user_id"] == "42"
        assert d["is_new_user"] is True

    def test_both_click_types_have_occurred_at(self):
        for et in ("referral.clicked", "referral.attributed"):
            event = ReferralClickEvent(event_type=et)
            assert event.occurred_at  # non-empty


# ── AdminAuditEvent schema ─────────────────────────────────────────────────────


class TestAdminAuditEvent:
    def test_serialises_user_suspended(self):
        event = AdminAuditEvent(
            event_type="admin.user_suspended",
            actor_user_id="1",
            target_type="user",
            target_id="99",
            notes="repeated TOS violations",
            ip_address="1.2.3.4",
        )
        d = dataclasses.asdict(event)
        assert d["event_type"] == "admin.user_suspended"
        assert d["actor_user_id"] == "1"
        assert d["target_id"] == "99"
        assert d["notes"] == "repeated TOS violations"

    def test_optional_previous_and_new_value(self):
        event = AdminAuditEvent(
            event_type="admin.user_role_changed",
            actor_user_id="1",
            target_type="user",
            target_id="2",
            previous_value="member",
            new_value="admin",
        )
        d = dataclasses.asdict(event)
        assert d["previous_value"] == "member"
        assert d["new_value"] == "admin"

    def test_optional_fields_default_to_none_or_empty(self):
        event = AdminAuditEvent(
            event_type="admin.content_flagged",
            actor_user_id="1",
            target_type="content",
            target_id="show-abc",
        )
        d = dataclasses.asdict(event)
        assert d["previous_value"] is None
        assert d["new_value"] is None
        assert d["notes"] == ""

    def test_emits_to_audit_topic(self):
        mock_pub = MagicMock()
        with patch("events.emit.get_publisher", return_value=mock_pub):
            emit(TOPIC_AUDIT, AdminAuditEvent(event_type="admin.user_deleted"))
        topic_arg = mock_pub.publish.call_args[0][0]
        assert topic_arg == TOPIC_AUDIT
