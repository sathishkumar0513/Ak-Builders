# Load Celery app when Django starts (only if celery is installed).
try:
    from .celery import app as celery_app  # noqa: F401

    __all__ = ("celery_app",)
except ImportError:  # pragma: no cover
    pass
