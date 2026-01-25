import os
from pathlib import Path
import environ

# ------------------------------------------------------------
# Paths / Env
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    WHITENOISE_MANIFEST_STRICT=(bool, False),
    DEBUG_PROPAGATE_EXCEPTIONS=(bool, False),
)

# IMPORTANT:
# Only read .env locally (DEBUG=True). In Render/production, use Render env vars.
DEBUG = env.bool("DJANGO_DEBUG", default=True)

if DEBUG:
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        environ.Env.read_env(str(env_file))

# ------------------------------------------------------------
# Core Security / Hosts
# ------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY")  # must exist in env vars (Render or local .env)

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=[
        "localhost",
        "127.0.0.1",
        "colrealty-website.onrender.com",  # Render service URL
    ],
)

# Do NOT default to propagating exceptions in production
DEBUG_PROPAGATE_EXCEPTIONS = env.bool("DEBUG_PROPAGATE_EXCEPTIONS", default=False)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # Must match your actual Render URL(s)
    CSRF_TRUSTED_ORIGINS = env.list(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        default=["https://colrealty-website.onrender.com"],
    )

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

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
# Fail-fast in production so you don't silently fall back to sqlite
if not DEBUG:
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
# 2) WhiteNoise local static collection (recommended for Render unless you truly use S3)
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

    # If using django-storages, typically use these:
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    STATICFILES_STORAGE = "storages.backends.s3boto3.S3StaticStorage"

else:
    # WhiteNoise / local static collection
    STATIC_URL = "/static/"
    STATIC_ROOT = BASE_DIR / "staticfiles"
    STATICFILES_DIRS = [BASE_DIR / "static"]

    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

    # Consistent STORAGES definition
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }

    # Safety valve while fixing manifest/static issues
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
