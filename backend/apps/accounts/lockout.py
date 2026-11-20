"""
Per-account lockout on top of the per-IP login throttle.

After LOGIN_MAX_FAILURES wrong passwords for the same username/email within LOGIN_LOCKOUT_MINUTES,
that account is locked for LOGIN_LOCKOUT_MINUTES — even if the attacker changes IP address.
A successful login (or an admin password reset) clears the counter.
"""

from django.conf import settings
from django.core.cache import cache


def _key(username):
    return f"login-fail:{str(username or '').strip().lower()[:150]}"


def _window():
    return getattr(settings, "LOGIN_LOCKOUT_MINUTES", 15) * 60


def is_locked(username):
    return cache.get(_key(username), 0) >= getattr(settings, "LOGIN_MAX_FAILURES", 5)


def register_failure(username):
    key = _key(username)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, _window())
        count = 1
    if count == getattr(settings, "LOGIN_MAX_FAILURES", 5):
        cache.touch(key, _window())  # lock period starts from the last failure
    return count


def clear(username):
    cache.delete(_key(username))
