import os
from pathlib import Path
import os
GOOGLE_MAPS_API_KEY=os.getenv("GOOGLE_MAPS_API_KEY")


import environ
from django.core.exceptions import ImproperlyConfigured

# ------------------------------------------------------------
# Paths / Env
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_READ_DOTENV=(bool, None),  # default handled below
    WHITENOISE_MANIFEST_STRICT=(bool, False),
    DEBUG_PROPAGATE_EXCEPTIONS=(bool, False),
)

def _require_env(name: str) -> str:
    """Fail fast when a required env var is missing (especially in production)."""
    val = os.environ.get(name)
    if val is None or str(val).strip() == "":
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return val

# ------------------------------------------------------------
# Environment mode
# ------------------------------------------------------------
# Keep default DEBUG=True so local dev works even if you haven't set env vars yet.
# In live, set DJANGO_DEBUG=False explicitly.
DEBUG = env.bool("DJANGO_DEBUG", default=True)

# Read .env only when explicitly allowed.
# Recommended:
#   - Local dev: let this default to True (because DEBUG=True)
#   - Live: set DJANGO_READ_DOTENV=False (or just ensure no .env file exists)
_read_dotenv_default = True if DEBUG else False
READ_DOTENV = env.bool("DJANGO_READ_DOTENV", default=_read_dotenv_default)

if READ_DOTENV:
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        environ.Env.read_env(str(env_file))

# ------------------------------------------------------------
# Core Security / Hosts
# ------------------------------------------------------------
# Required in all environments (local can be provided via .env)
SECRET_KEY = env("DJANGO_SECRET_KEY", default=None)
if not SECRET_KEY:
    # In production, do not allow blank secret key
    _require_env("DJANGO_SECRET_KEY")
    SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# Only allow localhost by default; everything else should come from env.
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"],
)

DEBUG_PROPAGATE_EXCEPTIONS = env.bool("DEBUG_PROPAGATE_EXCEPTIONS", default=False)

# Production security bits (works behind ALB / Nginx / reverse proxy)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # REQUIRED in production (avoid silent misconfig)
    if not os.environ.get("DJANGO_ALLOWED_HOSTS"):
        _require_env("DJANGO_ALLOWED_HOSTS")

    CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
    if not CSRF_TRUSTED_ORIGINS:
        _require_env("DJANGO_CSRF_TRUSTED_ORIGINS")

# ------------------------------------------------------------
# Applications
# ------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "listings",
    "pages",
    "mls_sync",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # keep it near the top
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ------------------------------------------------------------
# Database
# ------------------------------------------------------------
# Fail-fast in production so you don't silently fall back to sqlite.
if not DEBUG:
    _require_env("DATABASE_URL")
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    }

# ------------------------------------------------------------
# Password validation
# ------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------
# Internationalization
# ------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------
# Static / Media
# ------------------------------------------------------------
# Two supported modes:
# 1) S3 (if AWS_STORAGE_BUCKET_NAME is set)
# 2) WhiteNoise local static collection
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")

if AWS_STORAGE_BUCKET_NAME:
    INSTALLED_APPS += ["storages"]

    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN")  # optional (CloudFront)

    STATIC_LOCATION = "static"
    MEDIA_LOCATION = "media"

    if AWS_S3_CUSTOM_DOMAIN:
        STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{STATIC_LOCATION}/"
        MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{MEDIA_LOCATION}/"
    else:
        STATIC_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{STATIC_LOCATION}/"
        MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{MEDIA_LOCATION}/"

    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    STATICFILES_STORAGE = "storages.backends.s3boto3.S3StaticStorage"

else:
    STATIC_URL = "/static/"
    STATIC_ROOT = BASE_DIR / "staticfiles"
    STATICFILES_DIRS = [BASE_DIR / "static"]

    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

    WHITENOISE_MANIFEST_STRICT = env.bool("WHITENOISE_MANIFEST_STRICT", default=False)

# ------------------------------------------------------------
# MLS Connection
# ------------------------------------------------------------
MLS_API_BASE_URL = env("MLS_API_BASE_URL", default="")
MLS_API_TOKEN = env("MLS_API_TOKEN", default="")
MLS_ORIGINATING_SYSTEM_NAME = env("MLS_ORIGINATING_SYSTEM_NAME", default="actris")

# ------------------------------------------------------------
# Django defaults
# ------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
