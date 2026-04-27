import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent.parent

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DEBUG = os.environ.get("DEBUG", "True") == "True"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
DEVELOPMENT_MODE = DEBUG

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-change-me-before-production",
)

AUTH_USER_MODEL = "core.MBUser"

NEW_SHOW_DAYS = int(os.environ.get("NEW_SHOW_DAYS", 14))

# GCP
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
EVENTS_BIGQUERY_DATASET = os.environ.get(
    "EVENTS_BIGQUERY_DATASET", "movbits_events_dev"
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
    "allauth.socialaccount.providers.tiktok",
    "allauth.socialaccount.providers.instagram",
    "invitations",
    "anymail",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "siteconfigs",
    "integrations",
    "vendor",
    "storages",
    # Local apps
    "core",
    "events",
    "wallet",
    "shortlink",
    "team",
    "maintenance.apps.MaintenanceConfig",
    "survey",
    "administration",
    "analytics",
    "billing",
    "history",
    "localization",
    "shows",
    "support",
    "site_invitations",
    "media",
]

SITE_ID = 1

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.sites.middleware.CurrentSiteMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "maintenance.middleware.MaintenanceMiddleware",
    "core.middleware.SuperuserMFARequiredMiddleware",
]

ROOT_URLCONF = "movbitsapi.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "movbitsapi.wsgi.application"

# ── Database ──────────────────────────────────────────────────────────────────
# Defaults to SQLite for local dev; set DATABASE_URL for Postgres (Cloud SQL).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

if os.environ.get("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.config(conn_max_age=600)

# ── Auth ──────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("de", _("German")),
    ("en", _("English")),
    ("es", _("Spanish")),
    ("fr", _("French")),
    ("ja", _("Japanese")),
    ("ko", _("Korean")),
    ("pt", _("Portuguese")),
    ("zh-hans", _("Simplified Chinese")),
]

# ── Static / Media ────────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Security ──────────────────────────────────────────────────────────────────
ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "*").split(",") if h]

if not DEVELOPMENT_MODE:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── S3 / Storage ──────────────────────────────────────────────────────────────
# TODO (GCP task): migrate to Google Cloud Storage.
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None
AWS_STATIC_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_MEDIA_BUCKET_NAME = (
    os.environ.get("AWS_MEDIA_BUCKET_NAME") or AWS_STATIC_BUCKET_NAME
)
AWS_QUERYSTRING_AUTH = True

CLOUDFRONT_DOMAIN = os.environ.get("AWS_CLOUDFRONT_DOMAIN", "")
CLOUDFRONT_KEY_PAIR_ID = os.environ.get("AWS_CLOUDFRONT_KEY_PAIR_ID", "")
CLOUDFRONT_PRIVATE_KEY = os.environ.get("AWS_CLOUDFRONT_PRIVATE_KEY", "").replace(
    "\\n", "\n"
)
CLOUDFRONT_COOKIE_DOMAIN = os.environ.get("AWS_CLOUDFRONT_COOKIE_DOMAIN", "")
CLOUDFRONT_SIGNED_COOKIE_TTL = int(os.environ.get("AWS_CLOUDFRONT_COOKIE_TTL", "3600"))

STORAGES = {
    "default": {
        "BACKEND": "core.storage_backends.MediaStorage",
        "OPTIONS": {
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "bucket_name": AWS_MEDIA_BUCKET_NAME,
            "region_name": AWS_S3_REGION_NAME,
            "default_acl": AWS_DEFAULT_ACL,
            "file_overwrite": AWS_S3_FILE_OVERWRITE,
            "querystring_auth": True,
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

if AWS_STATIC_BUCKET_NAME:
    STATIC_URL = os.environ.get(
        "DJANGO_STATIC_URL",
        f"https://{AWS_STATIC_BUCKET_NAME}.s3.amazonaws.com/static/",
    )
    MEDIA_URL = os.environ.get(
        "DJANGO_MEDIA_URL",
        f"https://{AWS_MEDIA_BUCKET_NAME}.s3.amazonaws.com/",
    )

# ── Email ─────────────────────────────────────────────────────────────────────
if DEVELOPMENT_MODE:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
    ANYMAIL = {
        "MAILGUN_API_KEY": os.environ.get("MAILGUN_API_KEY"),
        "MAILGUN_SENDER_DOMAIN": os.environ.get("MAILGUN_DOMAIN"),
    }
DEFAULT_FROM_EMAIL = os.environ.get(
    "DJANGO_DEFAULT_FROM_EMAIL", "MovBits Support <support@movbits.com>"
)

# ── AllAuth ───────────────────────────────────────────────────────────────────
ACCOUNT_ADAPTER = "core.accounts.adapter.StoryAccountAdapter"
SOCIALACCOUNT_ADAPTER = "core.accounts.adapter.StorySocialAccountAdapter"
MFA_ADAPTER = "core.mfa_adapter.MovbitsMFAAdapter"
MFA_TOTP_ISSUER = "MovBits"
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SPA_BASE_URL = (
    "http://localhost:3000" if DEVELOPMENT_MODE else "https://www.movbits.com"
)

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
    "facebook": {
        "SCOPE": ["email", "public_profile"],
        "METHOD": "oauth2",
    },
    "tiktok": {
        "SCOPE": ["user.info.basic", "user.info.profile", "user.info.stats"],
    },
    "instagram": {
        "SCOPE": ["user_profile"],
    },
}

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*", "username"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_CONFIRM_EMAIL_ON_GET = True

_sso_providers_env = os.environ.get("SSO_ENABLED_PROVIDERS", "")
SSO_ENABLED_PROVIDERS: list = [
    p.strip() for p in _sso_providers_env.split(",") if p.strip()
]

LOGIN_REDIRECT_URL = (
    "http://localhost:3000/" if DEVELOPMENT_MODE else "https://www.movbits.com/"
)
ACCOUNT_LOGOUT_REDIRECT_URL = LOGIN_REDIRECT_URL

# ── REST Framework ────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

REST_AUTH = {
    "REGISTER_SERIALIZER": "core.api.serializers.RegisterSerializer",
    "PASSWORD_RESET_CONFIRM_URL": "reset-password?uid={uid}&token={token}",
    "PASSWORD_RESET_SERIALIZER": "core.api.serializers.SPAPasswordResetSerializer",
    "USE_JWT": True,
    "JWT_AUTH_COOKIE": None,
    "JWT_AUTH_REFRESH_COOKIE": None,
    "JWT_AUTH_HTTPONLY": False,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MovBits API",
    "DESCRIPTION": "Auto-generated OpenAPI schema",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000",
    ).split(",")
    if o.strip()
]

from corsheaders.defaults import default_headers  # noqa: E402

CORS_ALLOW_HEADERS = list(default_headers) + ["x-session-id"]

# ── Stripe ────────────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_123")
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "pk_test_123")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_123")

# ── Invitations ───────────────────────────────────────────────────────────────
INVITATIONS_INVITATION_MODEL = "site_invitations.SiteInvitation"
INVITATIONS_ADAPTER = "site_invitations.adapter.SiteInvitationAdapter"
INVITATIONS_INVITATION_EXPIRY = 7
MIGRATION_MODULES = {
    "invitations": None,
}

# ── Maintenance mode ──────────────────────────────────────────────────────────
MAINTENANCE_MODE = os.environ.get("MAINTENANCE_MODE", "False") == "True"
MAINTENANCE_BYPASS_PATHS = [
    "/api/admin/",
    "/api/health/",
    "/admin/",
]

# ── Redis / Event machine ─────────────────────────────────────────────────────

# ── GCP Pub/Sub ───────────────────────────────────────────────────────────────
PUBSUB_TOPIC_OVERRIDES: dict = {}
EVENTS_USE_LOGGING_FALLBACK = not bool(GCP_PROJECT_ID)

# ── Vendor ────────────────────────────────────────────────────────────────────
VENDOR_PRODUCT_MODEL = "billing.Product"
VENDOR_COUNTRY_CHOICE = ["US", "CA"]
VENDOR_COUNTRY_DEFAULT = "US"
VENDOR_CURRENCY_DEFAULT = "usd"

# ── Integrations ─────────────────────────────────────────────────────────────
ENCRYPTED_FIELD_KEYS = os.environ.get(
    "INTEGRATIONS_ENCRYPTED_FIELD_KEYS",
    "hUHBFZ9jSBk5uaokc013kVQwDk6RdTkY4CiRPFqFkzc=",
).split(",")

# ── Video access window ───────────────────────────────────────────────────────
VIDEO_ACCESS_WINDOW_HOURS = int(os.environ.get("VIDEO_ACCESS_WINDOW_HOURS", 24))

# ── Logging ───────────────────────────────────────────────────────────────────
if DEVELOPMENT_MODE:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {"format": "%(asctime)s [%(levelname)s] %(name)s %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
        },
        "root": {"handlers": ["console"], "level": LOG_LEVEL},
        "loggers": {
            "stripe": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "vendor": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "events": {"handlers": ["console"], "level": "INFO", "propagate": False},
        },
    }
else:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": (
                    "%(asctime)s %(levelname)s %(name)s %(message)s %(environment)s %(service)s"
                ),
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
        },
        "root": {"handlers": ["console"], "level": LOG_LEVEL},
        "loggers": {
            "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
            "stripe": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "vendor": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "events": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "app": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        },
    }
