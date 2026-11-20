import pytest

from apps.accounts.models import Role
from apps.core.models import AuditLog

pytestmark = pytest.mark.django_db
URL = "/api/v1/settings/company/"


def test_everyone_reads_only_management_writes(auth_client):
    sales, _ = auth_client(Role.SALES)
    assert sales.get(URL).status_code == 200
    assert sales.patch(URL, {"name": "X"}, format="json").status_code == 403
    admin, _ = auth_client(Role.ADMIN)
    r = admin.patch(
        URL, {"name": "AK Builders", "gstin": "33ABCDE1234F1Z5", "state_code": "33"}, format="json"
    )
    assert r.status_code == 200 and r.data["state"] == "Tamil Nadu"
    assert AuditLog.objects.filter(model_name="core.CompanySettings", action="UPDATE").exists()


def test_gstin_must_match_state(auth_client):
    admin, _ = auth_client(Role.ADMIN)
    r = admin.patch(URL, {"gstin": "32ABCDE1234F1Z5", "state_code": "33"}, format="json")
    assert r.status_code == 400 and "gstin" in r.data["errors"]


def test_sequences_super_admin_only_edit(auth_client):
    from django.core.management import call_command

    call_command("seed_data")
    admin, _ = auth_client(Role.ADMIN)
    seqs = admin.get("/api/v1/settings/sequences/").data
    assert len(seqs) >= 7 and seqs[0]["preview"].count("/") >= 2
    assert (
        admin.patch(
            f"/api/v1/settings/sequences/{seqs[0]['id']}/", {"prefix": "ARB"}, format="json"
        ).status_code
        == 403
    )
    boss, _ = auth_client(Role.SUPER_ADMIN)
    assert (
        boss.patch(
            f"/api/v1/settings/sequences/{seqs[0]['id']}/", {"prefix": "ARB"}, format="json"
        ).status_code
        == 200
    )


def test_audit_log_api_filters(auth_client):
    admin, _ = auth_client(Role.ADMIN)
    admin.patch(URL, {"name": "AK Builders Pvt"}, format="json")
    r = admin.get("/api/v1/audit-logs/", {"model_name": "core.CompanySettings"})
    assert r.status_code == 200 and r.data["count"] >= 1
    assert r.data["results"][0]["user_name"]


def test_states_have_names_only_and_cities_are_suggested(auth_client):
    from apps.customers.models import Customer

    client, _ = auth_client()
    states = client.get("/api/v1/lookups/").data["states"]
    assert states[0] == {"value": "33", "label": "Tamil Nadu"}  # home state first
    assert all(not s["label"][:2].isdigit() for s in states)
    Customer.objects.create(name="Ravi", phone="9876500001", state_code="33", city="Millerpuram")
    cities = client.get("/api/v1/lookups/cities/?state=33").data
    assert "Thoothukudi" in cities and "Millerpuram" in cities and cities == sorted(cities, key=str.lower)
    assert "Kochi" in client.get("/api/v1/lookups/cities/?state=32").data
    assert client.get("/api/v1/lookups/cities/?state=99").data == []
