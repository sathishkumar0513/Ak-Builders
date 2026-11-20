from decouple import config
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, SECRET_KEY

DEBUG = False

# Render tells the app its own address; accept it without extra setup
RENDER_HOST = config("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_HOST and RENDER_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_HOST)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_HOST}")

# Refuse to start with the sample key or without real host names
if SECRET_KEY in ("", "change-me-in-env") or len(SECRET_KEY) < 40:
    raise ImproperlyConfigured(
        'Set a long random SECRET_KEY in .env (python -c "import secrets; '
        'print(secrets.token_urlsafe(50))").'
    )
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set ALLOWED_HOSTS in .env to your domain / server IP.")

# HTTPS-ready: enable these once the site is behind SSL (set USE_HTTPS=True in .env)
USE_HTTPS = config("USE_HTTPS", default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = USE_HTTPS
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]  # host health checks call over plain HTTP
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS
SECURE_HSTS_SECONDS = 31536000 if USE_HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = USE_HTTPS
SECURE_HSTS_PRELOAD = False  # opt in only after HTTPS has run fine for a while
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Errors and security events go to the console (Docker / systemd collect them)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING"},
        "django.request": {"handlers": ["console"], "level": "ERROR"},
    },
}

# Uploads (site photos, bills, logo, avatars): free hosts wipe their disk on every restart,
# so when CLOUDINARY_URL is set the files go to Cloudinary instead of the local media folder.
USE_CLOUDINARY = bool(config("CLOUDINARY_URL", default=""))
STORAGES = {
    "default": {
        "BACKEND": (
            "cloudinary_storage.storage.MediaCloudinaryStorage"
            if USE_CLOUDINARY
            else "django.core.files.storage.FileSystemStorage"
        )
    },
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
