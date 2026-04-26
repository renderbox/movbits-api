"""
GCP / Cloud Run production settings.

Set DJANGO_SETTINGS_MODULE=movbitsapi.settings.gcp in Cloud Run environment.
All sensitive values must come from environment variables, which Cloud Run
populates from Secret Manager secrets (wired in the service configuration).
"""

import os

from .prod import *  # noqa: F401, F403

# ── Cloud SQL (Postgres via Unix socket) ──────────────────────────────────────
# Cloud Run injects DATABASE_URL when Cloud SQL Auth Proxy is configured.
# Format: postgresql://user:password@/dbname?host=/cloudsql/project:region:instance
# dj-database-url handles the socket path via the ?host= query parameter.
if not os.environ.get("DATABASE_URL"):
    raise RuntimeError(
        "DATABASE_URL must be set for GCP deployment. "
        "Wire a Cloud SQL connection in your Cloud Run service configuration."
    )

# ── ALLOWED_HOSTS ─────────────────────────────────────────────────────────────
# Cloud Run provides the service URL as CLOUD_RUN_SERVICE_URL.
# Add it automatically alongside any explicit ALLOWED_HOSTS entries.
_cloud_run_url = os.environ.get("CLOUD_RUN_SERVICE_URL", "")
_allowed = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]
if _cloud_run_url:
    from urllib.parse import urlparse
    _host = urlparse(_cloud_run_url).netloc
    if _host and _host not in _allowed:
        _allowed.append(_host)
ALLOWED_HOSTS = _allowed

# ── Google Cloud Storage (replaces S3 for prod) ───────────────────────────────
# TODO: uncomment when migrating from S3 to GCS.
# GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "")
# if GCS_BUCKET_NAME:
#     STORAGES["default"] = {
#         "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
#         "OPTIONS": {"bucket_name": GCS_BUCKET_NAME},
#     }
#     STORAGES["staticfiles"] = {
#         "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
#         "OPTIONS": {
#             "bucket_name": GCS_BUCKET_NAME,
#             "location": "static",
#             "default_acl": "publicRead",
#         },
#     }
#     STATIC_URL = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/static/"
#     MEDIA_URL = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/"

# ── Pub/Sub topic names ───────────────────────────────────────────────────────
# Override per-env topic names if your GCP project uses environment prefixes.
# PUBSUB_TOPIC_OVERRIDES = {
#     "analytics": "movbits-analytics-prod",
#     "revenue":   "movbits-revenue-prod",
#     "audit":     "movbits-audit-prod",
# }

# ── HTTPS / proxy headers ─────────────────────────────────────────────────────
# Cloud Run terminates TLS and forwards X-Forwarded-Proto.
SECURE_SSL_REDIRECT = False  # Cloud Run handles TLS termination
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── Security headers ──────────────────────────────────────────────────────────
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ── BigQuery dataset ──────────────────────────────────────────────────────────
EVENTS_BIGQUERY_DATASET = os.environ.get("EVENTS_BIGQUERY_DATASET", "movbits_events")
