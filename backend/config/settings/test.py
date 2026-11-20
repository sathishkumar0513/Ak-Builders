from .base import *  # noqa: F401,F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests
CELERY_TASK_ALWAYS_EAGER = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SECRET_KEY = "test-secret-key-that-is-long-enough-for-hs256-signing"
STATIC_ROOT.mkdir(parents=True, exist_ok=True)  # noqa: F405

# Generous limits so ordinary tests never hit them; throttle tests override per test.
REST_FRAMEWORK = {**REST_FRAMEWORK}  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    **REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
    "user": "100000/min",
    "anon": "100000/min",
    "export": "100000/min",
}
