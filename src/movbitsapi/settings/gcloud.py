"""
Local development settings using the Cloud SQL Auth Proxy.

Usage:
    # Terminal 1 — start the proxy
    cloud-sql-proxy movbits-dev:us-east1:movbits-dev --port 5432

    # Terminal 2 — run Django
    DJANGO_SETTINGS_MODULE=movbitsapi.settings.gcloud \
    DATABASE_URL="postgresql://movbits:PASSWORD@localhost:5432/movbits" \
    python manage.py runserver

Get the full DATABASE_URL (including the generated password) from Terraform:
    cd movbits-infra/environments/dev && terraform output -raw database_url
    Then replace the ?host=... suffix with @localhost:5432.
"""

import os

import dj_database_url

from .base import *  # noqa: F401, F403

# ── Database ──────────────────────────────────────────────────────────────────
_database_url = os.environ.get("DATABASE_URL")
if not _database_url:
    raise RuntimeError(
        "DATABASE_URL is not set.\n"
        "Start the Cloud SQL Auth Proxy and set:\n"
        "  DATABASE_URL=postgresql://movbits:PASSWORD@localhost:5432/movbits\n"
        "Get the password: cd movbits-infra/environments/dev && terraform output -raw database_url"
    )

# conn_max_age=0 avoids stale connections across proxy restarts during local dev
DATABASES["default"] = dj_database_url.config(conn_max_age=0)

# ── Relax security for local use ──────────────────────────────────────────────
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]
SECURE_SSL_REDIRECT = False
