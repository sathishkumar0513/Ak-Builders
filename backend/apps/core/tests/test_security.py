"""Security regression tests: lockout, tokens, uploads, data scoping, spreadsheet injection, throttles."""

import io
from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook
from PIL import Image

from apps.accounts.models import Role
from apps.customers.models import Customer
from apps.materials.models import Material, MaterialCategory
from apps.projects.models import Project
from conftest import PASSWORD

pytestmark = pytest.mark.django_db
LOGIN = "/api/v1/auth/login/"


def png_file(name="photo.png", size=(20, 20)):
    buf = io.BytesIO()
    Image.new("RGB", size, "orange").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


# ---------------------------------------------------------------------------
# login lockout & tokens
# ---------------------------------------------------------------------------
def test_account_locks_after_five_wrong_passwords(api, make_user, settings):
    settings.LOGIN_THROTTLE_RATE = "1000/min"
    make_user("ravi")
    make_user("mani")
    for i in range(5):
        api.credentials(REMOTE_ADDR=f"10.0.0.{i}")  # different IPs: the per-IP throttle doesn't help
        r = api.post(
            LOGIN, {"username": "ravi", "password": "wrong"}, format="json", REMOTE_ADDR=f"10.0.0.{i}"
        )
        assert r.status_code in (400, 401)
    # even the right password is refused while locked …
    r = api.post(LOGIN, {"username": "RAVI", "password": PASSWORD}, format="json", REMOTE_ADDR="10.0.1.1")
    assert r.status_code == 429 and "locked" in r.data["detail"]
    # … but other accounts are not affected
    r = api.post(LOGIN, {"username": "mani", "password": PASSWORD}, format="json", REMOTE_ADDR="10.0.1.2")
    assert r.status_code == 200
    from apps.core.models import AuditLog

    assert AuditLog.objects.filter(object_repr="Account locked: ravi").exists()


def test_successful_login_resets_failure_count(api, make_user):
    make_user("ravi")
    for i in range(4):
        api.post(LOGIN, {"username": "ravi", "password": "x"}, format="json", REMOTE_ADDR=f"10.1.0.{i}")
    assert (
        api.post(
            LOGIN, {"username": "ravi", "password": PASSWORD}, format="json", REMOTE_ADDR="10.1.1.1"
        ).status_code
        == 200
    )
    for i in range(4):
        api.post(LOGIN, {"username": "ravi", "password": "x"}, format="json", REMOTE_ADDR=f"10.1.2.{i}")
    assert (
        api.post(
            LOGIN, {"username": "ravi", "password": PASSWORD}, format="json", REMOTE_ADDR="10.1.3.1"
        ).status_code
        == 200
    )


def test_deactivated_user_tokens_stop_working(api, make_user):
    u = make_user("ravi")
    tokens = api.post(LOGIN, {"username": "ravi", "password": PASSWORD}, format="json").data
    u.is_active = False
    u.save()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert api.get("/api/v1/auth/me/").status_code == 401
    api.credentials()
    assert api.post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401


def test_forged_tokens_rejected(api, make_user):
    import base64
    import json

    make_user("ravi", role=Role.SALES)
    access = api.post(LOGIN, {"username": "ravi", "password": PASSWORD}, format="json").data["access"]
    head, body, sig = access.split(".")
    claims = json.loads(base64.urlsafe_b64decode(body + "=="))
    claims["role"] = Role.SUPER_ADMIN  # try to promote yourself
    forged_body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {head}.{forged_body}.{sig}")
    assert api.get("/api/v1/users/").status_code == 401
    none_head = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').decode().rstrip("=")
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {none_head}.{forged_body}.")
    assert api.get("/api/v1/users/").status_code == 401


def test_users_cannot_change_their_own_role(auth_client):
    client, user = auth_client(Role.SALES)
    client.patch("/api/v1/auth/me/", {"role": 1, "is_superuser": True, "first_name": "Ravi"}, format="json")
    user.refresh_from_db()
    assert user.role.code == Role.SALES and not user.is_superuser and user.first_name == "Ravi"


# ---------------------------------------------------------------------------
# uploads
# ---------------------------------------------------------------------------
@pytest.fixture
def project(make_user):
    eng = make_user("eng1", role=Role.SITE_ENGINEER)
    c = Customer.objects.create(name="Ravi", phone="9876500001")
    p = Project.objects.create(
        code="P1", name="Site", customer=c, site_address="x", contract_value=1000, assigned_engineer=eng
    )
    return p


def test_fake_images_are_rejected_and_real_ones_get_random_names(auth_client, project):
    client, _ = auth_client(Role.ADMIN)
    url = f"/api/v1/projects/{project.id}/add-progress/"
    fake = SimpleUploadedFile("site.jpg", b"<script>alert(1)</script>", content_type="image/jpeg")
    r = client.post(
        url, {"note": "x", "date": date.today().isoformat(), "photos": [fake]}, format="multipart"
    )
    assert r.status_code == 400
    svg = SimpleUploadedFile("x.png", b"<svg onload=alert(1)></svg>", content_type="image/png")
    r = client.post(url, {"note": "x", "date": date.today().isoformat(), "photos": [svg]}, format="multipart")
    assert r.status_code == 400
    r = client.post(
        url,
        {"note": "ok", "date": date.today().isoformat(), "photos": [png_file("my house.png")]},
        format="multipart",
    )
    assert r.status_code in (200, 201), r.data
    from apps.projects.models import ProgressPhoto

    name = ProgressPhoto.objects.get().image.name
    assert "my house" not in name and name.endswith(".png")


def test_expense_bill_must_really_be_pdf_or_photo(auth_client):
    client, _ = auth_client(Role.ACCOUNTANT)
    base = {"category": "SITE", "date": date.today().isoformat(), "amount": "100"}
    html = SimpleUploadedFile("bill.pdf", b"<html>phish</html>", content_type="application/pdf")
    assert (
        client.post("/api/v1/expenses/", {**base, "bill_attachment": html}, format="multipart").status_code
        == 400
    )
    pdf = SimpleUploadedFile("bill.pdf", b"%PDF-1.4\n%...", content_type="application/pdf")
    assert (
        client.post("/api/v1/expenses/", {**base, "bill_attachment": pdf}, format="multipart").status_code
        == 201
    )
    r = client.post("/api/v1/expenses/", {**base, "bill_attachment": png_file()}, format="multipart")
    assert r.status_code == 201


def test_logo_must_be_a_real_small_image(auth_client):
    client, _ = auth_client(Role.ADMIN)
    svg = SimpleUploadedFile(
        "logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", content_type="image/svg+xml"
    )
    assert client.patch("/api/v1/settings/company/", {"logo": svg}, format="multipart").status_code == 400
    r = client.patch("/api/v1/settings/company/", {"logo": png_file("logo.png")}, format="multipart")
    assert r.status_code == 200 and r.data["logo"].startswith("/media/company/")


def test_decompression_bomb_rejected():
    from apps.core.uploads import image_format

    buf = io.BytesIO()
    Image.new("1", (9000, 9000)).save(buf, "PNG")  # tiny file, 81 MP when opened
    f = SimpleUploadedFile("bomb.png", buf.getvalue(), content_type="image/png")
    assert image_format(f) is None


# ---------------------------------------------------------------------------
# data scoping (IDOR)
# ---------------------------------------------------------------------------
def test_site_engineer_cannot_reach_other_engineers_projects(api, project, make_user):
    other = make_user("eng2", role=Role.SITE_ENGINEER)
    api.force_authenticate(other)
    assert api.get(f"/api/v1/projects/{project.id}/").status_code == 404
    assert api.get(f"/api/v1/projects/{project.id}/materials/").status_code == 404
    r = api.post(
        f"/api/v1/projects/{project.id}/add-progress/",
        {"note": "x", "date": date.today().isoformat()},
        format="multipart",
    )
    assert r.status_code == 404


def test_cost_price_never_sent_to_sales_or_engineers(auth_client):
    cat = MaterialCategory.objects.create(name="Cement")
    Material.objects.create(category=cat, name="OPC", unit="bag", purchase_price=350, selling_price=400)
    for role in (Role.SALES, Role.SITE_ENGINEER):
        client, _ = auth_client(role)
        row = client.get("/api/v1/materials/").data["results"][0]
        assert "purchase_price" not in row and "stock_value" not in row


def test_odd_query_params_do_not_break_lists(auth_client):
    client, _ = auth_client(Role.ADMIN)
    for q in [
        "?search=' OR 1=1 --",
        "?ordering=password",
        "?ordering=;drop table",
        "?page=999",
        "?page=-1",
        "?page_size=100000",
        "?date_from=notadate",
    ]:
        r = client.get("/api/v1/customers/" + q)
        assert r.status_code in (200, 400, 404), (q, r.status_code)


# ---------------------------------------------------------------------------
# exports
# ---------------------------------------------------------------------------
def test_formula_injection_is_neutralised_in_excel(auth_client):
    from apps.invoices.services import create_invoice  # noqa: F401  (ensures app loaded)

    client, _ = auth_client(Role.ACCOUNTANT)
    Customer.objects.create(name='=HYPERLINK("http://evil","click")', phone="9876500009")
    from apps.payments.services import record_advance

    record_advance(
        customer=Customer.objects.get(phone="9876500009"), amount=100, date=date.today(), mode="CASH"
    )
    r = client.get("/api/v1/reports/payments/?export=xlsx")
    ws = load_workbook(io.BytesIO(r.content)).active
    values = [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)]
    evil = [v for v in values if "HYPERLINK" in v]
    assert evil and all(v.startswith("'") for v in evil)
    assert all(c.data_type != "f" for row in ws.iter_rows() for c in row)


def test_exports_are_rate_limited(auth_client, monkeypatch):
    from apps.reports.views import ExportThrottle

    monkeypatch.setattr(ExportThrottle, "THROTTLE_RATES", {"export": "2/min"})
    client, _ = auth_client(Role.ACCOUNTANT)
    codes = [client.get("/api/v1/reports/expenses/?export=pdf").status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert client.get("/api/v1/reports/expenses/").status_code == 200  # screen view still fine


# ---------------------------------------------------------------------------
# headers & settings
# ---------------------------------------------------------------------------
def test_security_headers(api):
    r = api.get("/api/v1/health/")
    assert r["X-Content-Type-Options"] == "nosniff"
    assert r["X-Frame-Options"] == "DENY"
    assert r["Referrer-Policy"] == "same-origin"


def test_production_settings_refuse_weak_secret(monkeypatch):
    import importlib
    import sys

    from django.core.exceptions import ImproperlyConfigured

    monkeypatch.setenv("SECRET_KEY", "change-me-in-env")
    for mod in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(mod, None)
    with pytest.raises(ImproperlyConfigured):
        importlib.import_module("config.settings.prod")
    for mod in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(mod, None)
