from decimal import Decimal as D

import pytest

from apps.accounts.models import Role
from apps.customers.models import Customer
from apps.materials.models import Material, MaterialCategory, StockMovement
from apps.projects.models import PaymentStage, Project

pytestmark = pytest.mark.django_db
TODAY = __import__("datetime").date.today().isoformat()
P = "/api/v1/projects/"


@pytest.fixture
def base(db):
    cat = MaterialCategory.objects.create(name="Steel")
    tmt = Material.objects.create(
        category=cat,
        name="TMT 12",
        brand="JSW",
        unit="kg",
        purchase_price=60,
        selling_price=68,
        gst_rate=18,
        stock_quantity=1000,
    )
    c = Customer.objects.create(name="Ravi", phone="9876500001", state_code="33")
    return {"tmt": tmt, "c": c}


def create_project(client, base, **kw):
    data = {
        "name": "Villa",
        "customer": base["c"].id,
        "site_address": "Plot 7, Millerpuram",
        "contract_value": "100000",
        "stages": [
            {"name": "Advance", "percentage": "30"},
            {"name": "Slab", "percentage": "40"},
            {"name": "Handover", "percentage": "30"},
        ],
    }
    data.update(kw)
    r = client.post(P, data, format="json")
    assert r.status_code == 201, r.data
    return r.data


def test_create_with_stages_and_validation(auth_client, base):
    admin, _ = auth_client(Role.ADMIN)
    p = create_project(admin, base)
    assert p["code"].startswith("AK/PRJ/") and [s["amount"] for s in p["payment_stages"]] == [
        "30000.00",
        "40000.00",
        "30000.00",
    ]
    r = admin.post(f"{P}{p['id']}/stages/", {"stages": [{"name": "A", "percentage": "60"}]}, format="json")
    assert r.status_code == 400 and "100%" in r.data["detail"]
    r = admin.patch(f"{P}{p['id']}/", {"contract_value": "120000"}, format="json")
    assert [s["amount"] for s in r.data["payment_stages"]] == ["36000.00", "48000.00", "36000.00"]


def test_engineer_sees_only_assigned_and_can_issue(auth_client, base):
    admin, _ = auth_client(Role.ADMIN)
    eng, engineer = auth_client(Role.SITE_ENGINEER)
    mine = create_project(admin, base, assigned_engineer=engineer.id)
    create_project(admin, base, name="Other site")
    assert [x["id"] for x in eng.get(P).data["results"]] == [mine["id"]]
    assert eng.patch(f"{P}{mine['id']}/", {"contract_value": "1"}, format="json").status_code == 403
    assert eng.get(f"{P}{mine['id']}/summary/").status_code == 403  # money is hidden from engineers

    r = eng.post(
        f"{P}{mine['id']}/issue-material/",
        {"material": base["tmt"].id, "quantity": "250", "notes": "Column steel"},
        format="json",
    )
    assert r.status_code == 201 and "amount" not in r.data  # cost hidden
    base["tmt"].refresh_from_db()
    assert base["tmt"].stock_quantity == D("750")
    mv = StockMovement.objects.get(movement_type="SITE_ISSUE")
    assert mv.project_id == mine["id"]
    too_much = eng.post(
        f"{P}{mine['id']}/issue-material/", {"material": base["tmt"].id, "quantity": "800"}, format="json"
    )
    assert too_much.status_code == 400
    back = eng.post(
        f"{P}{mine['id']}/issue-material/",
        {"material": base["tmt"].id, "quantity": "300", "is_return": True},
        format="json",
    )
    assert back.status_code == 400 and "Only 250" in back.data["detail"]
    eng.post(
        f"{P}{mine['id']}/issue-material/",
        {"material": base["tmt"].id, "quantity": "50", "is_return": True},
        format="json",
    )
    m = eng.get(f"{P}{mine['id']}/materials/").data
    assert m["summary"][0]["net"] == D("200") and "cost" not in m["summary"][0]

    note = eng.post(
        f"{P}{mine['id']}/add-progress/",
        {"note": "Plinth beam done", "progress_percent": "25"},
        format="multipart",
    )
    assert note.status_code == 201
    p = Project.objects.get(pk=mine["id"])
    assert p.progress_percent == D("25") and p.status == "IN_PROGRESS"


def test_progress_photo_upload(auth_client, base):
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    admin, _ = auth_client(Role.ADMIN)
    p = create_project(admin, base)
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), "orange").save(buf, "JPEG")
    photo = SimpleUploadedFile("site.jpg", buf.getvalue(), content_type="image/jpeg")
    bad = SimpleUploadedFile("x.txt", b"hello", content_type="text/plain")
    assert (
        admin.post(
            f"{P}{p['id']}/add-progress/", {"note": "x", "photos": [bad]}, format="multipart"
        ).status_code
        == 400
    )
    r = admin.post(
        f"{P}{p['id']}/add-progress/", {"note": "Tiles laid", "photos": [photo]}, format="multipart"
    )
    assert r.status_code == 201 and r.data["photos"][0]["image"].startswith("/media/projects/")


def test_stage_invoice_and_summary(auth_client, base):
    admin, _ = auth_client(Role.ADMIN)
    p = create_project(admin, base)
    stage = p["payment_stages"][0]  # 30,000
    r = admin.post("/api/v1/invoices/from-stage/", {"payment_stage": stage["id"]}, format="json")
    assert r.status_code == 201, r.data
    inv = r.data
    assert inv["grand_total"] == "30000.00" and inv["project"] == p["id"]
    assert (
        admin.post("/api/v1/invoices/from-stage/", {"payment_stage": stage["id"]}, format="json").status_code
        == 400
    )
    admin.post(
        "/api/v1/payments/",
        {
            "customer": base["c"].id,
            "invoice": inv["id"],
            "amount": "30000",
            "date": TODAY,
            "mode": "BANK",
        },
        format="json",
    )
    s = PaymentStage.objects.get(pk=stage["id"])
    assert s.status == "PAID" and s.amount_received == D("30000")
    # direct stage payment (no invoice) on stage 2
    st2 = p["payment_stages"][1]
    r = admin.post(
        "/api/v1/payments/",
        {
            "customer": base["c"].id,
            "payment_stage": st2["id"],
            "amount": "50000",
            "date": TODAY,
            "mode": "CASH",
        },
        format="json",
    )
    assert r.status_code == 400  # more than the stage
    admin.post(
        "/api/v1/payments/",
        {
            "customer": base["c"].id,
            "payment_stage": st2["id"],
            "amount": "10000",
            "date": TODAY,
            "mode": "CASH",
        },
        format="json",
    )
    assert PaymentStage.objects.get(pk=st2["id"]).status == "PARTIAL"
    admin.post(
        f"{P}{p['id']}/issue-material/", {"material": base["tmt"].id, "quantity": "100"}, format="json"
    )
    summ = admin.get(f"{P}{p['id']}/summary/").data
    assert summ["billed"] == D("30000.00") and summ["received"] == D("40000.00")
    assert summ["material_cost"] == D("6000.00") and summ["unbilled"] == D("70000.00")
    assert summ["expected_profit"] == D("94000.00")
    # stage with money can't be removed or re-percentaged
    r = admin.post(
        f"{P}{p['id']}/stages/",
        {
            "stages": [
                {"id": stage["id"], "name": "Advance", "percentage": "50"},
                {"name": "Rest", "percentage": "50"},
            ]
        },
        format="json",
    )
    assert r.status_code == 400
