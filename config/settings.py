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

BASE_DIR = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# django-environ setup
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
    val = os.environ.get(name)
    if val is None or str(val).strip() == "":
        raise ImproperlyConfigured(
            f"Missing required environment variable: {name}")
    return val


# ─────────────────────────────────────────────────────────────────────────────
# Environment mode
# ─────────────────────────────────────────────────────────────────────────────

DEBUG = env.bool("DJANGO_DEBUG", default=True)

_read_dotenv_default = True if DEBUG else False
READ_DOTENV = env.bool("DJANGO_READ_DOTENV", default=_read_dotenv_default)

if READ_DOTENV:
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        environ.Env.read_env(str(env_file))


# ─────────────────────────────────────────────────────────────────────────────
# Third-party API keys
# ─────────────────────────────────────────────────────────────────────────────

GOOGLE_MAPS_API_KEY = env("GOOGLE_MAPS_API_KEY", default="")
HUBSPOT_PRIVATE_APP_TOKEN = env("HUBSPOT_PRIVATE_APP_TOKEN", default="")
HUBSPOT_AGENT_NOTIFICATION_EMAIL_ID = env(
    "HUBSPOT_AGENT_NOTIFICATION_EMAIL_ID", default="")
LEAD_NOTIFY_EMAIL = env("LEAD_NOTIFY_EMAIL", default="")


# ─────────────────────────────────────────────────────────────────────────────
# Security
# ─────────────────────────────────────────────────────────────────────────────

SECRET_KEY = env("DJANGO_SECRET_KEY", default=None)
if not SECRET_KEY:
    _require_env("DJANGO_SECRET_KEY")
    SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

allowed_hosts_raw = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost")
ALLOWED_HOSTS = [host.strip()
                 for host in allowed_hosts_raw.split(",") if host.strip()]

DEBUG_PROPAGATE_EXCEPTIONS = env.bool(
    "DEBUG_PROPAGATE_EXCEPTIONS", default=False)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    if not os.environ.get("DJANGO_ALLOWED_HOSTS"):
        _require_env("DJANGO_ALLOWED_HOSTS")

    CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
    if not CSRF_TRUSTED_ORIGINS:
        _require_env("DJANGO_CSRF_TRUSTED_ORIGINS")


# ─────────────────────────────────────────────────────────────────────────────
# Installed Applications
# ─────────────────────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    "accounts",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
    "allauth.socialaccount.providers.apple",
    "django_celery_results",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    "leads",
    "listings",
    "mls_sync",
    "newsletter",
    "rentals",
    "pages",
    "portal",
    "ai_concierge",
    "common",
]


# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────

MIDDLEWARE = [
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ─────────────────────────────────────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.export_vars",
            ],
        },
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

if not DEBUG:
    _require_env("DATABASE_URL")
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
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
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ─────────────────────────────────────────────────────────────────────────────
# Static & Media files
#
# Two modes depending on whether AWS_STORAGE_BUCKET_NAME is set:
#   1. S3 mode    → static + media served from S3
#   2. WhiteNoise → static files served by Django/WhiteNoise (local dev)
# ─────────────────────────────────────────────────────────────────────────────

AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")

if AWS_STORAGE_BUCKET_NAME:
    # ── S3 mode ───────────────────────────────────────────────────────────
    INSTALLED_APPS += ["storages"]

    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN")

    _base_url = (
        f"https://{AWS_S3_CUSTOM_DOMAIN}"
        if AWS_S3_CUSTOM_DOMAIN
        else f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    )

    STATIC_URL = f"{_base_url}/static/"
    MEDIA_URL = f"{_base_url}/media/"

    STATIC_ROOT = BASE_DIR / "staticfiles"
    STATICFILES_DIRS = [BASE_DIR / "static"]

    STORAGES = {
        # Media files → media/ prefix in S3
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "region_name": AWS_S3_REGION_NAME,
                "location": "media",
                "file_overwrite": False,
                "querystring_auth": False,
            },
        },
        # Static files → static/ prefix in S3
        "staticfiles": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "region_name": AWS_S3_REGION_NAME,
                "location": "static",
                "file_overwrite": True,
                "querystring_auth": False,
            },
        },
    }

else:
    # ── WhiteNoise local mode ─────────────────────────────────────────────
    STATIC_URL = "/static/"
    STATIC_ROOT = BASE_DIR / "staticfiles"
    STATICFILES_DIRS = [BASE_DIR / "static"]

    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage"
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }

    WHITENOISE_MANIFEST_STRICT = env.bool(
        "WHITENOISE_MANIFEST_STRICT", default=False)


# ─────────────────────────────────────────────────────────────────────────────
# MLS Sync
# ─────────────────────────────────────────────────────────────────────────────

MLS_API_BASE_URL = env("MLS_API_BASE_URL", default="")
MLS_API_TOKEN = env("MLS_API_TOKEN", default="")
MLS_ORIGINATING_SYSTEM_NAME = env(
    "MLS_ORIGINATING_SYSTEM_NAME", default="actris")


# ─────────────────────────────────────────────────────────────────────────────
# Email — Gmail SMTP
# ─────────────────────────────────────────────────────────────────────────────

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL",
                         default=EMAIL_HOST_USER or "no-reply@colrealty.com")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)


# ─────────────────────────────────────────────────────────────────────────────
# Django defaults
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ─────────────────────────────────────────────────────────────────────────────
# Celery
# ─────────────────────────────────────────────────────────────────────────────

from kombu import Queue  # noqa: E402

CELERY_BROKER_URL = env("CELERY_BROKER_URL",
                        default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUES = (
    Queue("default"),
    Queue("hubspot"),
)

SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_LOGOUT_ON_GET = True
LOGIN_REDIRECT_URL = "/accounts/overview/"
LOGOUT_REDIRECT_URL = "/"
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = False
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
