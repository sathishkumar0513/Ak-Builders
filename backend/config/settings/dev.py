from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = False  # keep explicit origins even in dev
STATIC_ROOT.mkdir(parents=True, exist_ok=True)  # noqa: F405 — silences whitenoise warning
