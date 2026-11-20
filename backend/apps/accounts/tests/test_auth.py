import re

import pytest
from django.core import mail

from apps.accounts.models import Role
from apps.core.models import AuditLog
from conftest import PASSWORD

pytestmark = pytest.mark.django_db
LOGIN = "/api/v1/auth/login/"


def login(api, username, password=PASSWORD):
    return api.post(LOGIN, {"username": username, "password": password}, format="json")


def test_login_with_username_and_email(api, make_user):
    make_user("ravi", role=Role.ACCOUNTANT)
    r = login(api, "ravi")
    assert r.status_code == 200
    assert {"access", "refresh", "user"} <= set(r.data)
    assert r.data["user"]["role_code"] == "ACCOUNTANT"
    assert login(api, "RAVI@test.local").status_code == 200  # email, case-insensitive
    assert AuditLog.objects.filter(action="LOGIN", object_id=str(r.data["user"]["id"])).count() == 2


def test_wrong_password_is_rejected_and_audited(api, make_user):
    make_user("ravi")
    r = login(api, "ravi", "wrong")
    assert r.status_code == 401
    assert r.data["detail"] == "Invalid username/email or password."
    assert AuditLog.objects.filter(action="LOGIN_FAIL").exists()


def test_inactive_and_deleted_users_cannot_login(api, make_user):
    make_user("off", is_active=False)
    make_user("gone", is_deleted=True)
    assert login(api, "off").status_code == 401
    assert login(api, "gone").status_code == 401


def test_login_is_rate_limited(api, make_user):
    make_user("ravi")
    codes = [login(api, "ravi", "bad").status_code for _ in range(6)]
    assert codes[-1] == 429


def test_refresh_rotates_and_logout_blacklists(api, make_user):
    make_user("ravi")
    tokens = login(api, "ravi").data
    r = api.post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert r.status_code == 200 and r.data["refresh"] != tokens["refresh"]
    # old refresh token was blacklisted by rotation
    assert api.post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401

    api.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    assert api.post("/api/v1/auth/logout/", {"refresh": r.data["refresh"]}, format="json").status_code == 205
    assert api.post("/api/v1/auth/refresh/", {"refresh": r.data["refresh"]}, format="json").status_code == 401


def test_me_get_and_update(auth_client):
    client, user = auth_client(Role.SALES)
    assert client.get("/api/v1/auth/me/").data["username"] == user.username
    r = client.patch("/api/v1/auth/me/", {"first_name": "Selvi", "phone": "9876543210"}, format="json")
    assert r.status_code == 200 and r.data["first_name"] == "Selvi"
    # cannot promote yourself through /me
    client.patch("/api/v1/auth/me/", {"role": 1, "is_active": False}, format="json")
    user.refresh_from_db()
    assert user.role.code == Role.SALES and user.is_active


def test_change_password(api, make_user):
    user = make_user("ravi", must_change_password=True)
    tokens = login(api, "ravi").data
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    bad = api.post(
        "/api/v1/auth/change-password/",
        {"old_password": "nope", "new_password": "N3w!Pass#2026", "confirm_password": "N3w!Pass#2026"},
        format="json",
    )
    assert bad.status_code == 400 and "old_password" in bad.data["errors"]
    r = api.post(
        "/api/v1/auth/change-password/",
        {"old_password": PASSWORD, "new_password": "N3w!Pass#2026", "confirm_password": "N3w!Pass#2026"},
        format="json",
    )
    assert r.status_code == 200 and "access" in r.data
    user.refresh_from_db()
    assert user.check_password("N3w!Pass#2026") and not user.must_change_password
    # old refresh token no longer works (other devices logged out)
    assert api.post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401


def test_weak_password_rejected(auth_client):
    client, _ = auth_client(Role.SALES)
    r = client.post(
        "/api/v1/auth/change-password/",
        {"old_password": PASSWORD, "new_password": "12345678", "confirm_password": "12345678"},
        format="json",
    )
    assert r.status_code == 400


def test_forgot_and_reset_password(api, make_user):
    user = make_user("ravi")
    r = api.post("/api/v1/auth/forgot-password/", {"email": "ravi@test.local"}, format="json")
    assert r.status_code == 200 and len(mail.outbox) == 1
    # unknown email gives the same answer and sends nothing
    api.post("/api/v1/auth/forgot-password/", {"email": "nobody@test.local"}, format="json")
    assert len(mail.outbox) == 1

    uid, token = re.search(r"/reset-password/([^/]+)/(\S+)", mail.outbox[0].body).groups()
    payload = {
        "uid": uid,
        "token": token,
        "new_password": "R3set!Pass#26",
        "confirm_password": "R3set!Pass#26",
    }
    assert api.post("/api/v1/auth/reset-password/", payload, format="json").status_code == 200
    user.refresh_from_db()
    assert user.check_password("R3set!Pass#26")
    # link cannot be used twice
    assert api.post("/api/v1/auth/reset-password/", payload, format="json").status_code == 400


def test_unauthenticated_requests_get_401(api):
    assert api.get("/api/v1/auth/me/").status_code == 401
    assert api.get("/api/v1/users/").status_code == 401
