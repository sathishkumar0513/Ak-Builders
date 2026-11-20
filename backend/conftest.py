import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Role, User

PASSWORD = "Str0ng!Pass#2026"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()  # resets DRF throttle counters between tests
    yield
    cache.clear()


@pytest.fixture
def roles(db):
    data = {}
    for code, name in Role.CODE_CHOICES:
        data[code], _ = Role.objects.get_or_create(code=code, defaults={"name": name})
    return data


@pytest.fixture
def make_user(roles):
    def _make(username, role=Role.SALES, password=PASSWORD, **extra):
        user = User.objects.create_user(
            username=username, email=f"{username}@test.local", password=password, role=roles[role], **extra
        )
        return user

    return _make


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def auth_client(make_user):
    """auth_client(role) → (client logged in as a new user with that role, user)."""

    def _client(role=Role.ADMIN, username=None):
        user = make_user(username or f"u_{role.lower()}", role=role)
        client = APIClient()
        client.force_authenticate(user)
        return client, user

    return _client
