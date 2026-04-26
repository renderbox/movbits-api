"""
BigQuery direct-write publisher with a logging fallback for development and testing.

In production, set GCP_PROJECT_ID in the environment. If it is absent or
EVENTS_USE_LOGGING_FALLBACK is True, events are written to the Django logger
instead — useful for local dev and CI.

On Heroku (or any non-GCP host), also set GOOGLE_APPLICATION_CREDENTIALS_JSON to
the full contents of a service account key JSON file. On GCP the publisher uses
Application Default Credentials automatically.

Topic → BigQuery table mapping (dataset configured via EVENTS_BIGQUERY_DATASET):
  analytics  → chapter_playback
  revenue    → chapter_unlocked
  audit      → auth_and_admin

Usage:
    from events.pubsub import get_publisher
    get_publisher().publish("analytics", {"event_type": "chapter.started", ...})
"""

import json
import logging
import os
from typing import Any

from django.conf import settings

logger = logging.getLogger("events.pubsub")

_TOPIC_TABLE_MAP = {
    "analytics": "chapter_playback",
    "revenue": "chapter_unlocked",
    "purchases": "credit_purchases",
    "referrals": "referral_clicks",
    "errors": "app_errors",
    "audit": "auth_and_admin",
    "engagement": "show_engagement",
}


class LoggingPublisher:
    """Writes events to the Django logger instead of BigQuery."""

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        logger.info(
            "EVENT [%s]: %s",
            topic,
            json.dumps(payload, default=str),
        )


class PubSubPublisher:
    """Publishes events to GCP Pub/Sub (retained for future use)."""

    def __init__(self, project_id: str) -> None:
        from google.cloud import pubsub_v1  # type: ignore[import]

        self._client = pubsub_v1.PublisherClient()
        self._project_id = project_id

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        topic_path = self._client.topic_path(self._project_id, topic)
        data = json.dumps(payload, default=str).encode("utf-8")
        future = self._client.publish(topic_path, data)
        future.result()


class BigQueryPublisher:
    """
    Writes events directly to BigQuery via the streaming insert API.

    Credentials are resolved in order:
      1. GOOGLE_APPLICATION_CREDENTIALS_JSON env var (JSON string) — Heroku / CI
      2. Application Default Credentials — GCP-hosted environments
    """

    def __init__(self, project_id: str) -> None:
        from google.cloud import bigquery  # type: ignore[import]

        self._project_id = project_id
        self._dataset = getattr(settings, "EVENTS_BIGQUERY_DATASET", "movbits_events")

        creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "")
        if creds_json:
            from google.oauth2 import service_account  # type: ignore[import]

            info = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/bigquery"],
            )
            self._client = bigquery.Client(project=project_id, credentials=credentials)
        else:
            self._client = bigquery.Client(project=project_id)

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        table_name = _TOPIC_TABLE_MAP.get(topic)
        if not table_name:
            logger.warning(
                "BigQueryPublisher: unknown topic %r — dropping event", topic
            )
            return

        table_ref = f"{self._project_id}.{self._dataset}.{table_name}"
        errors = self._client.insert_rows_json(table_ref, [payload])
        if errors:
            logger.error(
                "BigQuery insert errors for table %s: %s",
                table_ref,
                errors,
            )


_publisher: LoggingPublisher | PubSubPublisher | BigQueryPublisher | None = None


def get_publisher() -> LoggingPublisher | PubSubPublisher | BigQueryPublisher:
    global _publisher
    if _publisher is None:
        project_id = getattr(settings, "GCP_PROJECT_ID", None)
        use_fallback = getattr(settings, "EVENTS_USE_LOGGING_FALLBACK", not project_id)
        if project_id and not use_fallback:
            _publisher = BigQueryPublisher(project_id)
        else:
            _publisher = LoggingPublisher()
    return _publisher


def reset_publisher() -> None:
    """Force re-initialisation on the next call to get_publisher(). Tests only."""
    global _publisher
    _publisher = None
