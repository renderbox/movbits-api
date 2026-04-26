import os

from .base import *  # noqa: F401, F403

DEBUG = False
DEVELOPMENT_MODE = False

ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]

EVENTS_BIGQUERY_DATASET = "movbits_events"
