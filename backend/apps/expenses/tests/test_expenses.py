from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import Role
from apps.customers.models import Customer
from apps.projects.models import Project
from apps.projects.services import project_summary

pytestmark = pytest.mark.django_db
TODAY = date.today().isoformat()


@pytest.fixture
def site(make_user):
    eng = make_user("eng1", role=Role.SITE_ENGINEER)
    other_eng = make_user("eng2", role=Role.SITE_ENGINEER)
    c = Customer.objects.create(name="Ravi", phone="9876500001")
    mine = Project.objects.create(
        code="P1", name="Mine", customer=c, site_address="x", contract_value=100000, assigned_engineer=eng
    )
    theirs = Project.objects.create(
        code="P2",
        name="Theirs",
        customer=c,
        site_address="y",
        contract_value=50000,
        assigned_engineer=other_eng,
    )
    return {"eng": eng, "mine": mine, "theirs": theirs}


def _exp(project=None, **kw):
    data = {
        "category": "LABOUR",
        "date": TODAY,
        "amount": "2500",
        "paid_to": "Mason team",
        "mode": "CASH",
        "workers_count": 5,
        "work_days": "1",
    }
    if project:
        data["project"] = project.id
    data.update(kw)
    return data


def test_office_expense_is_numbered_and_auto_approved(auth_client):
    client, _ = auth_client(Role.ACCOUNTANT)
    r = client.post("/api/v1/expenses/", _exp(category="OFFICE"), format="json")
    assert r.status_code == 201, r.data
    assert r.data["voucher_number"].startswith("AK/EXP/")
    assert r.data["is_approved"] is True


def test_engineer_flow_and_scoping(api, site, auth_client):
    api.force_authenticate(site["eng"])
    # must choose a project, and only their own
    assert api.post("/api/v1/expenses/", _exp(), format="json").status_code == 400
    assert api.post("/api/v1/expenses/", _exp(site["theirs"]), format="json").status_code == 400
    r = api.post("/api/v1/expenses/", _exp(site["mine"]), format="json")
    assert r.status_code == 201 and r.data["is_approved"] is False
    eid = r.data["id"]
    # editable until approved
    assert api.patch(f"/api/v1/expenses/{eid}/", {"amount": "2600"}, format="json").status_code == 200
    # can't approve or delete
    assert api.post(f"/api/v1/expenses/{eid}/approve/").status_code == 403
    assert api.delete(f"/api/v1/expenses/{eid}/").status_code == 403

    acc, _ = auth_client(Role.ACCOUNTANT)
    acc.post("/api/v1/expenses/", _exp(site["theirs"], amount="999"), format="json")
    summary = acc.get("/api/v1/expenses/summary/?approved=false").data
    assert summary["pending_approval"] == 1 and D(summary["total"]) == D("2600")
    assert acc.post(f"/api/v1/expenses/{eid}/approve/").status_code == 200
    # locked for the engineer after approval
    assert api.patch(f"/api/v1/expenses/{eid}/", {"amount": "1"}, format="json").status_code == 400
    # engineer only sees their project's expenses
    assert [e["id"] for e in api.get("/api/v1/expenses/").data["results"]] == [eid]
    # project cost picks it up
    assert project_summary(site["mine"])["expenses"] == D("2600")


def test_rules(auth_client, site):
    client, _ = auth_client(Role.ACCOUNTANT)
    future = (date.today() + timedelta(days=2)).isoformat()
    assert client.post("/api/v1/expenses/", _exp(date=future), format="json").status_code == 400
    assert client.post("/api/v1/expenses/", _exp(amount="0"), format="json").status_code == 400
    site["mine"].status = Project.Status.CANCELLED
    site["mine"].save()
    assert client.post("/api/v1/expenses/", _exp(site["mine"]), format="json").status_code == 400
    bad = SimpleUploadedFile("a.exe", b"MZ", content_type="application/x-msdownload")
    r = client.post("/api/v1/expenses/", {**_exp(), "bill_attachment": bad}, format="multipart")
    assert r.status_code == 400
    ok = SimpleUploadedFile("bill.pdf", b"%PDF-1.4", content_type="application/pdf")
    r = client.post("/api/v1/expenses/", {**_exp(), "bill_attachment": ok}, format="multipart")
    assert r.status_code == 201 and r.data["bill_attachment"].startswith("/media/expenses/")


def test_delete_is_soft_and_admin_only(auth_client):
    acc, _ = auth_client(Role.ACCOUNTANT)
    eid = acc.post("/api/v1/expenses/", _exp(), format="json").data["id"]
    assert acc.delete(f"/api/v1/expenses/{eid}/").status_code == 403
    admin, _ = auth_client(Role.ADMIN)
    assert admin.delete(f"/api/v1/expenses/{eid}/").status_code == 204
    from apps.expenses.models import Expense

    assert Expense.all_objects.get(pk=eid).is_deleted
