"""Stores the request user in a context variable so models/signals can fill created_by."""

from contextvars import ContextVar

_current_user = ContextVar("current_user", default=None)
_current_ip = ContextVar("current_ip", default=None)


def get_current_user():
    user = _current_user.get()
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    return None


def get_current_ip():
    return _current_ip.get()


def set_current_user(user):
    """Used by JWT-authenticated DRF views (request.user is only resolved inside DRF)."""
    _current_user.set(user)


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
        t_user = _current_user.set(getattr(request, "user", None))
        t_ip = _current_ip.set(ip)
        try:
            return self.get_response(request)
        finally:
            _current_user.reset(t_user)
            _current_ip.reset(t_ip)
