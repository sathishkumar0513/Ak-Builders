from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from django.core import mail
from django.core.management import call_command

from apps.accounts.models import Role
from apps.core.models import AuditLog, TermsTemplate
from apps.customers.models import Customer
from apps.materials.models import Material, MaterialCategory
from apps.projects.models import PaymentStage, Project
from apps.quotations.models import Quotation

pytestmark = pytest.mark.django_db
Q = "/api/v1/quotations/"


@pytest.fixture
def data(db):
    cat = MaterialCategory.objects.create(name="Cement")
    cement = Material.objects.create(
        category=cat,
        name="OPC 53",
        brand="UltraTech",
        hsn_code="2523",
        unit="bag",
        purchase_price=370,
        selling_price=410,
        gst_rate=18,
    )
    local = Customer.objects.create(
        name="Ravi Kumar", phone="9876500001", state_code="33", address="VOC Street", email="ravi@example.com"
    )
    kerala = Customer.objects.create(name="Joseph", phone="9876500002", state_code="32")
    TermsTemplate.objects.create(title="Std", applies_to="QUOTATION", content="30% advance.", is_default=True)
    return {"cement": cement, "local": local, "kerala": kerala}


def payload(d, customer="local", **kw):
    p = {
        "customer": d[customer].id,
        "title": "Kitchen renovation",
        "header_discount": "500",
        "items": [
            {"material": d["cement"].id, "quantity": "20", "rate": "410"},
            {
                "item_type": "SERVICE",
                "description": "Plastering labour",
                "hsn_code": "995456",
                "quantity": "300",
                "unit": "sqft",
                "rate": "25",
                "gst_rate": "18",
            },
        ],
    }
    p.update(kw)
    return p


def create(client, d, **kw):
    r = client.post(Q, payload(d, **kw), format="json")
    assert r.status_code == 201, r.data
    return r.data


def test_create_defaults_and_totals(auth_client, data):
    client, _ = auth_client(Role.SALES)
    q = create(client, data)
    assert q["number"].startswith("AK/QT/2026-27/") or q["number"].startswith("AK/QT/")
    assert q["revision"] == 1 and q["status"] == "DRAFT" and q["is_latest"]
    assert q["valid_until"] == str(date.today() + timedelta(days=15))
    assert q["terms_and_conditions"] == "30% advance." and q["site_address"] == "VOC Street"
    # 8200 + 7500 = 15700 − 500 header discount = 15200 taxable → GST 2736 → 17936
    assert (
        q["subtotal"] == "15700.00" and q["discount_total"] == "500.00" and q["taxable_amount"] == "15200.00"
    )
    # per-line rounding: the odd paisa of each line goes to CGST, total tax is still exactly 18%
    assert (q["cgst_amount"], q["sgst_amount"], q["igst_amount"]) == ("1368.01", "1367.99", "0.00")
    assert q["grand_total"] == "17936.00"
    assert q["items"][0]["description"] == "OPC 53 UltraTech" and q["items"][0]["unit"] == "bag"
    assert "send" in q["allowed_actions"] and "convert" not in q["allowed_actions"]


def test_other_state_customer_gets_igst(auth_client, data):
    client, _ = auth_client(Role.SALES)
    q = create(client, data, customer="kerala", header_discount="0")
    assert q["is_interstate"] and q["igst_amount"] == "2826.00" and q["place_of_supply"] == "32"


def test_header_discount_cannot_exceed_value(auth_client, data):
    client, _ = auth_client(Role.SALES)
    r = client.post(Q, payload(data, header_discount="99999"), format="json")
    assert r.status_code == 400 and "header_discount" in r.data["errors"]


def test_draft_edit_and_locked_after_send(auth_client, data):
    client, _ = auth_client(Role.SALES)
    q = create(client, data)
    r = client.patch(f"{Q}{q['id']}/", {"header_discount": "0"}, format="json")
    assert r.status_code == 200 and r.data["grand_total"] == "18526.00"
    assert client.post(f"{Q}{q['id']}/send/").data["status"] == "SENT"
    r = client.patch(f"{Q}{q['id']}/", {"title": "x"}, format="json")
    assert r.status_code == 400 and "revision" in r.data["detail"]


def test_revision_flow(auth_client, data):
    client, _ = auth_client(Role.SALES)
    q = create(client, data)
    client.post(f"{Q}{q['id']}/send/")
    assert client.post(f"{Q}{q['id']}/revise/").status_code == 201
    rev2 = Quotation.objects.get(number=q["number"], revision=2)
    old = Quotation.objects.get(pk=q["id"])
    assert rev2.status == "DRAFT" and rev2.is_latest and not old.is_latest and old.status == "SENT"
    assert rev2.items.count() == 2 and rev2.grand_total == old.grand_total
    # list shows only latest revision; old revision cannot change status
    listed = client.get(Q).data["results"]
    assert [(x["number"], x["revision"]) for x in listed] == [(q["number"], 2)]
    assert client.get(Q, {"all_revisions": "true"}).data["count"] == 2
    assert client.post(f"{Q}{old.pk}/approve/").status_code == 400
    detail = client.get(f"{Q}{rev2.pk}/").data
    assert [r["revision"] for r in detail["revisions"]] == [1, 2]
    # rev 3 after rejecting rev 2
    client.post(f"{Q}{rev2.pk}/reject/", {"reason": "Too costly"}, format="json")
    assert client.post(f"{Q}{rev2.pk}/revise/").data["revision"] == 3


def test_status_rules(auth_client, data):
    client, _ = auth_client(Role.SALES)
    q = create(client, data)
    assert client.post(f"{Q}{q['id']}/revise/").status_code == 400  # drafts are edited, not revised
    r = client.post(f"{Q}{q['id']}/reject/", {"reason": "Customer postponed"}, format="json")
    assert r.data["status"] == "REJECTED" and r.data["rejection_reason"] == "Customer postponed"
    assert client.post(f"{Q}{q['id']}/approve/").status_code == 400
    assert AuditLog.objects.filter(action="STATUS", object_id=str(q["id"])).exists()


def test_expiry(auth_client, data):
    client, _ = auth_client(Role.SALES)
    q = create(client, data)
    client.post(f"{Q}{q['id']}/send/")
    Quotation.objects.filter(pk=q["id"]).update(valid_until=date.today() - timedelta(days=1))
    call_command("expire_quotations")
    assert Quotation.objects.get(pk=q["id"]).status == "EXPIRED"
    assert client.post(f"{Q}{q['id']}/approve/").status_code == 400


def test_convert_to_project_with_default_stages(auth_client, data):
    sales, _ = auth_client(Role.SALES)
    admin, _ = auth_client(Role.ADMIN)
    eng, engineer = auth_client(Role.SITE_ENGINEER)
    q = create(sales, data)
    assert admin.post(f"{Q}{q['id']}/convert/").status_code == 400  # not approved yet
    sales.post(f"{Q}{q['id']}/approve/")
    assert sales.post(f"{Q}{q['id']}/convert/").status_code == 403  # management only
    r = admin.post(
        f"{Q}{q['id']}/convert/",
        {"assigned_engineer": engineer.id, "start_date": "2026-11-15"},
        format="json",
    )
    assert r.status_code == 201, r.data
    project = Project.objects.get(pk=r.data["project"]["id"])
    assert project.contract_value == D("17936.00") and project.customer_id == data["local"].id
    assert project.assigned_engineer == engineer and project.code.startswith("AK/PRJ/")
    stages = list(PaymentStage.objects.filter(project=project).order_by("sort_order"))
    assert [s.percentage for s in stages] == [D("30"), D("40"), D("30")]
    assert sum(s.amount for s in stages) == project.contract_value
    assert (
        r.data["quotation"]["status"] == "CONVERTED"
        and r.data["quotation"]["project"]["code"] == project.code
    )
    assert admin.post(f"{Q}{q['id']}/convert/").status_code == 400  # only once
    assert admin.post(f"{Q}{q['id']}/revise/").status_code == 400


def test_convert_custom_stages_must_total_100(auth_client, data):
    admin, _ = auth_client(Role.ADMIN)
    q = create(admin, data)
    admin.post(f"{Q}{q['id']}/approve/")
    bad = admin.post(f"{Q}{q['id']}/convert/", {"stages": [{"name": "A", "percentage": "50"}]}, format="json")
    assert bad.status_code == 400
    ok = admin.post(
        f"{Q}{q['id']}/convert/",
        {"stages": [{"name": "Advance", "percentage": "50"}, {"name": "Handover", "percentage": "50"}]},
        format="json",
    )
    assert ok.status_code == 201
    assert PaymentStage.objects.filter(project_id=ok.data["project"]["id"]).count() == 2


def test_pdf_and_share_text(auth_client, data):
    client, _ = auth_client(Role.SALES)
    q = create(client, data)
    r = client.get(f"{Q}{q['id']}/pdf/")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert r.content[:4] == b"%PDF" and len(r.content) > 5000
    assert "inline" in r["Content-Disposition"]
    assert "attachment" in client.get(f"{Q}{q['id']}/pdf/", {"download": "1"})["Content-Disposition"]
    share = client.get(f"{Q}{q['id']}/share-text/").data
    assert "₹17,936.00" in share["message"] and share["phone"] == "9876500001"


def test_email_sends_pdf_and_marks_sent(auth_client, data):
    client, _ = auth_client(Role.SALES)
    q = create(client, data)
    r = client.post(f"{Q}{q['id']}/email/", {"to": ["ravi@example.com"]}, format="json")
    assert r.status_code == 200 and r.data["status"] == "SENT"
    assert len(mail.outbox) == 1
    name, content, mime = mail.outbox[0].attachments[0]
    assert mime == "application/pdf" and content[:4] == b"%PDF" and name.endswith("-R1.pdf")


def test_duplicate_for_another_customer(auth_client, data):
    client, _ = auth_client(Role.SALES)
    q = create(client, data)
    r = client.post(f"{Q}{q['id']}/duplicate/", {"customer": data["kerala"].id}, format="json")
    assert r.status_code == 201 and r.data["number"] != q["number"] and r.data["is_interstate"]


def test_delete_rules_and_permissions(auth_client, data):
    sales, _ = auth_client(Role.SALES)
    admin, _ = auth_client(Role.ADMIN)
    eng, _ = auth_client(Role.SITE_ENGINEER)
    assert eng.get(Q).status_code == 403
    q = create(sales, data)
    assert sales.delete(f"{Q}{q['id']}/").status_code == 403
    admin.post(f"{Q}{q['id']}/approve/")
    assert admin.delete(f"{Q}{q['id']}/").status_code == 400
    q2 = create(sales, data)
    assert admin.delete(f"{Q}{q2['id']}/").status_code == 204
    assert sales.get(f"{Q}{q2['id']}/").status_code == 404


def test_deleting_latest_revision_reactivates_previous(auth_client, data):
    admin, _ = auth_client(Role.ADMIN)
    q = create(admin, data)
    admin.post(f"{Q}{q['id']}/send/")
    rev2 = admin.post(f"{Q}{q['id']}/revise/").data
    assert admin.delete(f"{Q}{rev2['id']}/").status_code == 204
    assert Quotation.objects.get(pk=q["id"]).is_latest


def test_terms_templates_single_default(auth_client, data):
    admin, _ = auth_client(Role.ADMIN)
    r = admin.post(
        "/api/v1/settings/terms/",
        {
            "title": "Labour only",
            "applies_to": "QUOTATION",
            "content": "Material by customer.",
            "is_default": True,
        },
        format="json",
    )
    assert r.status_code == 201
    assert TermsTemplate.objects.filter(applies_to="QUOTATION", is_default=True).count() == 1
    sales, _ = auth_client(Role.SALES)
    assert len(sales.get("/api/v1/settings/terms/", {"applies_to": "QUOTATION"}).data) == 2
    assert sales.post("/api/v1/settings/terms/", {}, format="json").status_code == 403


def test_user_lookup_for_engineer_picker(auth_client):
    sales, _ = auth_client(Role.SALES)
    auth_client(Role.SITE_ENGINEER, username="eng1")
    r = sales.get("/api/v1/users/lookup/", {"role": "SITE_ENGINEER"})
    assert r.status_code == 200 and [u["role_code"] for u in r.data] == ["SITE_ENGINEER"]
    assert sales.get("/api/v1/users/").status_code == 403
