import pytest

from apps.accounts.models import Role, User
from apps.core.models import AuditLog
from conftest import PASSWORD

pytestmark = pytest.mark.django_db
USERS = "/api/v1/users/"


def new_user_payload(roles, role=Role.SITE_ENGINEER, username="kumar"):
    return {
        "username": username,
        "email": f"{username}@test.local",
        "first_name": "Kumar",
        "phone": "9876500000",
        "role": roles[role].id,
        "password": "Temp!Pass#2026",
    }


@pytest.mark.parametrize("role", [Role.ACCOUNTANT, Role.SITE_ENGINEER, Role.SALES])
def test_non_admin_roles_cannot_manage_users(auth_client, role):
    client, _ = auth_client(role)
    assert client.get(USERS).status_code == 403
    assert client.get("/api/v1/audit-logs/").status_code == 403


def test_user_without_role_is_denied(make_user, api):
    user = make_user("norole")
    user.role = None
    user.save()
    api.force_authenticate(user)
    assert api.get(USERS).status_code == 403


def test_admin_creates_user_with_temporary_password(auth_client, roles, api):
    client, admin = auth_client(Role.ADMIN)
    r = client.post(USERS, new_user_payload(roles), format="json")
    assert r.status_code == 201, r.data
    assert r.data["role_code"] == "SITE_ENGINEER" and r.data["must_change_password"] is True
    assert AuditLog.objects.filter(action="CREATE", model_name="accounts.User", user=admin).exists()
    login = api.post(
        "/api/v1/auth/login/", {"username": "kumar", "password": "Temp!Pass#2026"}, format="json"
    )
    assert login.status_code == 200 and login.data["user"]["must_change_password"] is True


def test_duplicate_email_and_bad_phone_rejected(auth_client, roles, make_user):
    client, _ = auth_client(Role.ADMIN)
    make_user("kumar")
    r = client.post(USERS, {**new_user_payload(roles), "username": "kumar2", "phone": "12345"}, format="json")
    assert r.status_code == 400
    assert "email" in r.data["errors"] and "phone" in r.data["errors"]


def test_admin_cannot_create_or_touch_super_admin(auth_client, roles, make_user):
    client, _ = auth_client(Role.ADMIN)
    r = client.post(USERS, new_user_payload(roles, role=Role.SUPER_ADMIN), format="json")
    assert r.status_code == 400 and "role" in r.data["errors"]
    boss = make_user("boss", role=Role.SUPER_ADMIN)
    assert client.post(f"{USERS}{boss.id}/deactivate/").status_code == 400
    assert client.patch(f"{USERS}{boss.id}/", {"first_name": "X"}, format="json").status_code == 400


def test_super_admin_can_create_super_admin(auth_client, roles):
    client, _ = auth_client(Role.SUPER_ADMIN)
    r = client.post(USERS, new_user_payload(roles, role=Role.SUPER_ADMIN, username="boss2"), format="json")
    assert r.status_code == 201


def test_list_search_filter(auth_client, make_user):
    client, _ = auth_client(Role.ADMIN)
    make_user("anbu", role=Role.SALES, first_name="Anbu")
    make_user("bala", role=Role.ACCOUNTANT)
    r = client.get(USERS, {"search": "anbu"})
    assert r.status_code == 200 and r.data["count"] == 1
    r = client.get(USERS, {"role": "ACCOUNTANT"})
    assert [u["username"] for u in r.data["results"]] == ["bala"]


def test_deactivate_logs_user_out_and_blocks_login(auth_client, make_user, api):
    client, _ = auth_client(Role.ADMIN)
    worker = make_user("worker")
    tokens = api.post("/api/v1/auth/login/", {"username": "worker", "password": PASSWORD}, format="json").data
    assert client.post(f"{USERS}{worker.id}/deactivate/").status_code == 200
    assert api.post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert api.get("/api/v1/auth/me/").status_code == 401
    assert client.post(f"{USERS}{worker.id}/activate/").data["is_active"] is True


def test_cannot_deactivate_or_delete_self(auth_client):
    client, admin = auth_client(Role.ADMIN)
    assert client.post(f"{USERS}{admin.id}/deactivate/").status_code == 400
    assert client.delete(f"{USERS}{admin.id}/").status_code == 400


def test_last_super_admin_is_protected(make_user, api):
    only_boss = make_user("boss", role=Role.SUPER_ADMIN)
    # a Django superuser without a role row also counts as Super Admin (e.g. created with createsuperuser)
    root = User.objects.create_superuser("root", "root@test.local", PASSWORD)
    api.force_authenticate(root)
    r = api.post(f"{USERS}{only_boss.id}/deactivate/")
    assert r.status_code == 400 and "last active Super Admin" in r.data["detail"]
    make_user("boss2", role=Role.SUPER_ADMIN)
    assert api.post(f"{USERS}{only_boss.id}/deactivate/").status_code == 200


def test_soft_delete_hides_user(auth_client, make_user):
    client, _ = auth_client(Role.ADMIN)
    u = make_user("temp")
    assert client.delete(f"{USERS}{u.id}/").status_code == 204
    assert client.get(f"{USERS}{u.id}/").status_code == 404
    assert User.objects.filter(pk=u.pk, is_deleted=True, is_active=False).exists()


def test_admin_reset_password(auth_client, make_user, api):
    client, _ = auth_client(Role.ADMIN)
    u = make_user("forgetful")
    r = client.post(f"{USERS}{u.id}/reset-password/", {"new_password": "Temp!Pass#2027"}, format="json")
    assert r.status_code == 200
    login = api.post(
        "/api/v1/auth/login/", {"username": "forgetful", "password": "Temp!Pass#2027"}, format="json"
    )
    assert login.data["user"]["must_change_password"] is True


def test_roles_endpoint(auth_client):
    client, _ = auth_client(Role.ADMIN)
    assert len(client.get("/api/v1/roles/").data) == 5
