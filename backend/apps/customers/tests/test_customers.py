import pytest

from apps.accounts.models import Role
from apps.customers.models import Customer
from apps.payments.models import CustomerLedgerEntry

pytestmark = pytest.mark.django_db
URL = "/api/v1/customers/"


def payload(**kw):
    data = {"name": "Ravi  Kumar", "phone": "+91 98765 43210", "city": "Thoothukudi", "state_code": "33"}
    data.update(kw)
    return data


def test_sales_can_create_and_phone_is_normalised(auth_client):
    client, _ = auth_client(Role.SALES)
    r = client.post(URL, payload(), format="json")
    assert r.status_code == 201, r.data
    assert r.data["phone"] == "9876543210" and r.data["name"] == "Ravi Kumar"
    assert r.data["state_name"] == "Tamil Nadu"


def test_duplicate_phone_rejected_with_owner_name(auth_client):
    client, _ = auth_client(Role.SALES)
    client.post(URL, payload(), format="json")
    r = client.post(URL, payload(name="Other"), format="json")
    assert r.status_code == 400 and "Ravi Kumar" in r.data["errors"]["phone"][0]


def test_gstin_must_match_state_and_company_needs_contact(auth_client):
    client, _ = auth_client(Role.ADMIN)
    r = client.post(URL, payload(gstin="32abcde1234f1z5"), format="json")
    assert r.status_code == 400 and "gstin" in r.data["errors"]
    r = client.post(URL, payload(gstin="33abcde1234f1z5", customer_type="COMPANY"), format="json")
    assert r.status_code == 400 and "contact_person" in r.data["errors"]
    r = client.post(
        URL, payload(gstin="33abcde1234f1z5", customer_type="COMPANY", contact_person="Mani"), format="json"
    )
    assert r.status_code == 201 and r.data["gstin"] == "33ABCDE1234F1Z5"


def test_bad_phone_and_pincode(auth_client):
    client, _ = auth_client(Role.SALES)
    r = client.post(URL, payload(phone="12345", pincode="62800"), format="json")
    assert r.status_code == 400 and {"phone", "pincode"} <= set(r.data["errors"])


def test_search_filter_and_outstanding(auth_client):
    client, _ = auth_client(Role.ACCOUNTANT)
    a = Customer.objects.create(name="Anbu Builders", phone="9000000001", city="Madurai")
    Customer.objects.create(name="Bala", phone="9000000002", city="Thoothukudi")
    CustomerLedgerEntry.objects.create(
        customer=a,
        date="2026-11-01",
        entry_type="INVOICE",
        debit="15000",
        reference_type="Invoice",
        reference_id=1,
    )
    CustomerLedgerEntry.objects.create(
        customer=a,
        date="2026-11-02",
        entry_type="PAYMENT",
        credit="5000",
        reference_type="Payment",
        reference_id=1,
    )
    r = client.get(URL, {"search": "anbu"})
    assert r.data["count"] == 1 and r.data["results"][0]["outstanding"] == "10000.00"
    assert client.get(URL, {"city": "thoothukudi"}).data["count"] == 1
    assert client.get(URL, {"ordering": "-outstanding"}).data["results"][0]["name"] == "Anbu Builders"
    s = client.get(f"{URL}{a.id}/summary/").data
    assert s["outstanding"] == 10000 and s["counts"]["projects"] == 0


def test_permissions(auth_client):
    eng, _ = auth_client(Role.SITE_ENGINEER)
    assert eng.get(URL).status_code == 403
    sales, _ = auth_client(Role.SALES, username="s2")
    c = sales.post(URL, payload(), format="json").data
    assert sales.delete(f"{URL}{c['id']}/").status_code == 403  # only management deletes
    admin, _ = auth_client(Role.ADMIN)
    assert admin.delete(f"{URL}{c['id']}/").status_code == 204
    assert sales.get(f"{URL}{c['id']}/").status_code == 404
    assert admin.post(f"{URL}{c['id']}/restore/").status_code == 200
    assert sales.get(f"{URL}{c['id']}/").status_code == 200
