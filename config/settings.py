"""
config/settings.py
──────────────────
Django settings for the Col Realty web application.

Environment modes:
  - DEBUG=True  → local development (reads .env file automatically)
  - DEBUG=False → production on AWS EC2 (all secrets from environment variables)

Required environment variables in production:
  DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS,
  DATABASE_URL, CELERY_BROKER_URL,
  GOOGLE_MAPS_API_KEY, HUBSPOT_PRIVATE_APP_TOKEN,
  LEAD_NOTIFY_EMAIL, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
"""

import os
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

# Absolute path to the project root (the folder containing manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# django-environ setup
# Declares type casting and defaults for env() calls made throughout this file.
# ─────────────────────────────────────────────────────────────────────────────

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_READ_DOTENV=(bool, None),
    WHITENOISE_MANIFEST_STRICT=(bool, False),
    DEBUG_PROPAGATE_EXCEPTIONS=(bool, False),
    EMAIL_PORT=(int, 587),
    EMAIL_USE_TLS=(bool, True),
)


def _require_env(name: str) -> str:
    """
    Raise ImproperlyConfigured if a required env var is missing or blank.
    Used to fail-fast in production rather than silently use bad defaults.
    """
    val = os.environ.get(name)
    if val is None or str(val).strip() == "":
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return val


# ─────────────────────────────────────────────────────────────────────────────
# Environment mode
# DEBUG=True  → local dev  (auto-reads .env)
# DEBUG=False → production (env vars must be set on the server / AWS)
# ─────────────────────────────────────────────────────────────────────────────

DEBUG = env.bool("DJANGO_DEBUG", default=True)

# In DEBUG mode, automatically read the .env file from the project root.
# In production, env vars are injected by the server so .env is not needed.
_read_dotenv_default = True if DEBUG else False
READ_DOTENV = env.bool("DJANGO_READ_DOTENV", default=_read_dotenv_default)

if READ_DOTENV:
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        environ.Env.read_env(str(env_file))


# ─────────────────────────────────────────────────────────────────────────────
# Third-party API keys
# Read AFTER .env is loaded so local dev values are available.
# ─────────────────────────────────────────────────────────────────────────────

# Google Maps — used for property map views on Buy and Rent pages
GOOGLE_MAPS_API_KEY = env("GOOGLE_MAPS_API_KEY", default="")

# HubSpot — Private App token for CRM lead sync
# Get from: HubSpot → Settings → Integrations → Private Apps
HUBSPOT_PRIVATE_APP_TOKEN = env("HUBSPOT_PRIVATE_APP_TOKEN", default="")

# Optional: HubSpot transactional email template ID for agent notifications
# Get from: HubSpot → Marketing → Email → Transactional → [template] → Settings
# Leave blank to fall back to Django SMTP for agent emails
HUBSPOT_AGENT_NOTIFICATION_EMAIL_ID = env("HUBSPOT_AGENT_NOTIFICATION_EMAIL_ID", default="")

# Email address that receives new lead notifications (your agent's inbox)
LEAD_NOTIFY_EMAIL = env("LEAD_NOTIFY_EMAIL", default="")


# ─────────────────────────────────────────────────────────────────────────────
# Security
# ─────────────────────────────────────────────────────────────────────────────

# SECURITY WARNING: keep the secret key secret in production.
# Generate a new one with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY = env("DJANGO_SECRET_KEY", default=None)
if not SECRET_KEY:
    _require_env("DJANGO_SECRET_KEY")
    SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# Hosts/domains this Django site can serve.
# In production set: DJANGO_ALLOWED_HOSTS=54.82.48.58,colrealty.com,www.colrealty.com
allowed_hosts_raw = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost")
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_raw.split(",") if host.strip()]

DEBUG_PROPAGATE_EXCEPTIONS = env.bool("DEBUG_PROPAGATE_EXCEPTIONS", default=False)

# Production-only security settings — only active when DEBUG=False
if not DEBUG:
    # Tell Django to trust the X-Forwarded-Proto header from Nginx / AWS ALB
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # Ensure cookies are only sent over HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE    = True

    # Fail loudly if ALLOWED_HOSTS is not explicitly set in production
    if not os.environ.get("DJANGO_ALLOWED_HOSTS"):
        _require_env("DJANGO_ALLOWED_HOSTS")

    # Required for CSRF to work behind HTTPS reverse proxies.
    # Example: DJANGO_CSRF_TRUSTED_ORIGINS=https://colrealty.com,https://www.colrealty.com
    CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
    if not CSRF_TRUSTED_ORIGINS:
        _require_env("DJANGO_CSRF_TRUSTED_ORIGINS")


# ─────────────────────────────────────────────────────────────────────────────
# Installed Applications
# ─────────────────────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",         # template filters: intcomma, naturaltime, etc.

    # Col Realty apps
    "listings",                        # Buy property listings (MLS-synced)
    "rentals",                         # Rental listings
    "pages",                           # Static and marketing pages
    "leads",                           # Lead capture + HubSpot CRM sync
    "mls_sync",                        # Background MLS data synchronisation
    "portal",                          # Custom staff admin portal at /portal/

    # Third-party
    "django_celery_results",           # Stores Celery task results in the DB (visible in admin)
]


# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# Order matters — SecurityMiddleware and WhiteNoise must be near the top.
# ─────────────────────────────────────────────────────────────────────────────

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",   # serves static files in production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ─────────────────────────────────────────────────────────────────────────────
# URL / WSGI / ASGI
# ─────────────────────────────────────────────────────────────────────────────

ROOT_URLCONF  = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ─────────────────────────────────────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Global templates directory — takes priority over app-level templates/
        "DIRS": [BASE_DIR / "templates"],
        # Also look for templates/ inside each installed app
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.export_vars",  # custom: injects site-wide vars
            ],
        },
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# Database
# Uses DATABASE_URL env var (dj-database-url format).
# Examples:
#   Local dev SQLite:  DATABASE_URL=sqlite:///db.sqlite3
#   Production RDS:    DATABASE_URL=postgres://user:pass@rds-endpoint:5432/colrealty
# ─────────────────────────────────────────────────────────────────────────────

if not DEBUG:
    # In production, fail immediately if DATABASE_URL is missing
    _require_env("DATABASE_URL")
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    # In development, fall back to a local SQLite file if DATABASE_URL is not set
    DATABASES = {
        "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    }


# ─────────────────────────────────────────────────────────────────────────────
# Password validation
# ─────────────────────────────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Internationalisation
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGE_CODE = "en-us"
TIME_ZONE     = "UTC"
USE_I18N      = True
USE_TZ        = True


# ─────────────────────────────────────────────────────────────────────────────
# Static & Media files
#
# Two modes depending on whether AWS_STORAGE_BUCKET_NAME is set:
#   1. S3 mode      → static and media files served from S3 / CloudFront
#   2. WhiteNoise   → static files served by Django/WhiteNoise (simpler, no S3)
# ─────────────────────────────────────────────────────────────────────────────

AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")

if AWS_STORAGE_BUCKET_NAME:
    # ── S3 / CloudFront mode ──────────────────────────────────────────────
    INSTALLED_APPS += ["storages"]

    AWS_S3_REGION_NAME      = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_FILE_OVERWRITE   = False   # prevent overwriting files with the same name

    # Optional CloudFront CDN domain (faster global delivery)
    # Set AWS_S3_CUSTOM_DOMAIN=your-distribution.cloudfront.net to enable
    AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN")

    STATIC_LOCATION = "static"
    MEDIA_LOCATION  = "media"

    if AWS_S3_CUSTOM_DOMAIN:
        STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{STATIC_LOCATION}/"
        MEDIA_URL  = f"https://{AWS_S3_CUSTOM_DOMAIN}/{MEDIA_LOCATION}/"
    else:
        STATIC_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{STATIC_LOCATION}/"
        MEDIA_URL  = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{MEDIA_LOCATION}/"

    STORAGES = {
        "default":     {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "storages.backends.s3boto3.S3StaticStorage"},
    }

else:
    # ── WhiteNoise local mode ─────────────────────────────────────────────
    STATIC_URL  = "/static/"
    STATIC_ROOT = BASE_DIR / "staticfiles"   # collectstatic writes here
    STATICFILES_DIRS = [BASE_DIR / "static"] # source static files live here

    MEDIA_URL  = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

    STORAGES = {
        "default":    {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        # CompressedManifestStaticFilesStorage adds content-hash fingerprinting
        # for cache-busting on deploys
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

    # Set to True in production to raise errors on missing static files
    WHITENOISE_MANIFEST_STRICT = env.bool("WHITENOISE_MANIFEST_STRICT", default=False)


# ─────────────────────────────────────────────────────────────────────────────
# MLS Sync
# Credentials for the MLS RESO API used by mls_sync/
# ─────────────────────────────────────────────────────────────────────────────

MLS_API_BASE_URL = env("MLS_API_BASE_URL", default="")
MLS_API_TOKEN    = env("MLS_API_TOKEN", default="")
MLS_ORIGINATING_SYSTEM_NAME = env("MLS_ORIGINATING_SYSTEM_NAME", default="actris")


# ─────────────────────────────────────────────────────────────────────────────
# Email — Gmail SMTP
# Used for lead notification emails to agents.
# For Gmail, generate an App Password (not your account password):
#   Google Account → Security → 2-Step Verification → App Passwords
# ─────────────────────────────────────────────────────────────────────────────

EMAIL_BACKEND      = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST         = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT         = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS      = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER    = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER or "no-reply@colrealty.com")
SERVER_EMAIL       = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)


# ─────────────────────────────────────────────────────────────────────────────
# Django defaults
# ─────────────────────────────────────────────────────────────────────────────

# Use BigAutoField (64-bit int) as the default primary key type for all models
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ─────────────────────────────────────────────────────────────────────────────
# Celery — Async task queue
#
# Used for:
#   - HubSpot CRM lead sync (leads/tasks.py)
#   - MLS data sync (mls_sync/tasks.py)
#
# Broker: Redis
#   Local dev:    run Redis via Docker: docker run -d -p 6379:6379 redis
#   Production:   use AWS ElastiCache Redis endpoint
#
# Start worker (local Windows dev):
#   celery -A config worker -l info -Q default,hubspot --pool=solo
#
# Start worker (production Linux EC2 — managed by systemd):
#   celery -A config worker -l info -Q default,hubspot
# ─────────────────────────────────────────────────────────────────────────────

from kombu import Queue  # noqa: E402 — imported here to keep Celery config together

# Redis connection URLs
# Production: set CELERY_BROKER_URL=redis://<elasticache-endpoint>:6379/0
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")

# Store task results in the Django database (visible in /admin and /portal)
CELERY_RESULT_BACKEND  = "django-db"
CELERY_CACHE_BACKEND   = "django-cache"

# Serialisation — JSON is safe, human-readable, and works across all workers
CELERY_TASK_SERIALIZER   = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT    = ["json"]

# Use Django's timezone setting
CELERY_TIMEZONE = TIME_ZONE

# Task execution behaviour
CELERY_TASK_TRACK_STARTED         = True  # allows monitoring of in-progress tasks
CELERY_TASK_TIME_LIMIT            = 300   # hard kill after 5 minutes
CELERY_TASK_SOFT_TIME_LIMIT       = 240   # raises SoftTimeLimitExceeded at 4 min
CELERY_WORKER_PREFETCH_MULTIPLIER = 1     # one task at a time per worker — important for long tasks

# Named queues:
#   default  → general tasks (MLS sync, etc.)
#   hubspot  → CRM sync tasks (isolated so HubSpot API slowness never blocks MLS sync)
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUES = (
    Queue("default"),
    Queue("hubspot"),
)