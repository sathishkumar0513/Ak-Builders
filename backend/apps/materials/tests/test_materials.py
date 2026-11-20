from decimal import Decimal as D

import pytest

from apps.accounts.models import Role
from apps.core.exceptions import BusinessRuleError
from apps.materials.models import Material, MaterialCategory, PriceHistory, StockMovement
from apps.materials.services import record_movement

pytestmark = pytest.mark.django_db
URL = "/api/v1/materials/"


@pytest.fixture
def cement_cat(db):
    return MaterialCategory.objects.create(name="Cement")


def material_payload(cat, **kw):
    data = {
        "category": cat.id,
        "name": "OPC 53",
        "brand": "UltraTech",
        "hsn_code": "2523",
        "unit": "bag",
        "purchase_price": "370",
        "selling_price": "410",
        "gst_rate": "18",
        "reorder_level": "50",
    }
    data.update(kw)
    return data


def test_create_with_opening_stock(auth_client, cement_cat):
    client, _ = auth_client(Role.ACCOUNTANT)
    r = client.post(URL, material_payload(cement_cat, opening_stock="120"), format="json")
    assert r.status_code == 201, r.data
    assert r.data["stock_quantity"] == "120.000"
    mv = StockMovement.objects.get(material_id=r.data["id"])
    assert mv.movement_type == "OPENING" and mv.balance_after == D("120")


def test_validation(auth_client, cement_cat):
    client, _ = auth_client(Role.ADMIN)
    r = client.post(
        URL, material_payload(cement_cat, gst_rate="15", hsn_code="25A", selling_price="300"), format="json"
    )
    assert {"gst_rate", "hsn_code"} <= set(r.data["errors"])
    r = client.post(URL, material_payload(cement_cat, selling_price="300"), format="json")
    assert "selling_price" in r.data["errors"]
    assert (
        client.post(
            URL, material_payload(cement_cat, selling_price="300", allow_below_cost=True), format="json"
        ).status_code
        == 201
    )
    dup = client.post(URL, material_payload(cement_cat, brand="ultratech"), format="json")
    assert dup.status_code == 400 and "name" in dup.data["errors"]


def test_price_change_creates_history_and_stock_is_read_only(auth_client, cement_cat):
    client, _ = auth_client(Role.ACCOUNTANT)
    m = client.post(URL, material_payload(cement_cat), format="json").data
    r = client.patch(
        f"{URL}{m['id']}/",
        {"selling_price": "420", "price_change_reason": "Dealer rate up", "stock_quantity": "9999"},
        format="json",
    )
    assert (
        r.status_code == 200 and r.data["selling_price"] == "420.00" and r.data["stock_quantity"] == "0.000"
    )
    h = PriceHistory.objects.get(material_id=m["id"])
    assert (h.old_selling_price, h.new_selling_price, h.reason) == (D("410"), D("420"), "Dealer rate up")
    client.patch(f"{URL}{m['id']}/", {"name": "OPC 53 Grade"}, format="json")
    assert PriceHistory.objects.filter(material_id=m["id"]).count() == 1  # no price change → no history
    assert len(client.get(f"{URL}{m['id']}/price-history/").data) == 1


def test_purchase_price_hidden_from_sales_and_engineers(auth_client, cement_cat):
    Material.objects.create(
        category=cement_cat, name="PPC", brand="Ramco", purchase_price=355, selling_price=395
    )
    for role in (Role.SALES, Role.SITE_ENGINEER):
        client, _ = auth_client(role)
        row = client.get(URL).data["results"][0]
        assert "purchase_price" not in row and "stock_value" not in row
        assert client.post(URL, {}, format="json").status_code == 403
    acc, _ = auth_client(Role.ACCOUNTANT)
    assert "purchase_price" in acc.get(URL).data["results"][0]


def test_stock_adjustment_never_negative(auth_client, cement_cat):
    client, _ = auth_client(Role.ADMIN)
    m = client.post(URL, material_payload(cement_cat, opening_stock="10"), format="json").data
    r = client.post(
        f"{URL}{m['id']}/adjust-stock/",
        {"direction": "OUT", "quantity": "11", "reason": "Damaged"},
        format="json",
    )
    assert r.status_code == 400 and "available 10" in r.data["detail"]
    r = client.post(
        f"{URL}{m['id']}/adjust-stock/",
        {"direction": "OUT", "quantity": "3", "reason": "Damaged"},
        format="json",
    )
    assert r.status_code == 201 and r.data["balance_after"] == "7.000"
    acc, _ = auth_client(Role.ACCOUNTANT)
    assert (
        acc.post(
            f"{URL}{m['id']}/adjust-stock/",
            {"direction": "IN", "quantity": "1", "reason": "x"},
            format="json",
        ).status_code
        == 403
    )
    assert client.get(f"{URL}{m['id']}/movements/").data["count"] == 2


def test_low_stock_filter_and_endpoint(auth_client, cement_cat):
    client, _ = auth_client(Role.ADMIN)
    client.post(URL, material_payload(cement_cat, opening_stock="40"), format="json")  # reorder 50 → low
    client.post(URL, material_payload(cement_cat, brand="Dalmia", opening_stock="80"), format="json")
    assert client.get(URL, {"low_stock": "true"}).data["count"] == 1
    assert client.get(f"{URL}low-stock/").data["count"] == 1


def test_cannot_delete_material_with_stock(auth_client, cement_cat):
    client, _ = auth_client(Role.ADMIN)
    m = client.post(URL, material_payload(cement_cat, opening_stock="5"), format="json").data
    r = client.delete(f"{URL}{m['id']}/")
    assert r.status_code == 400 and "still has 5 bag" in r.data["detail"]


def test_record_movement_service_guards(cement_cat):
    m = Material.objects.create(category=cement_cat, name="X")
    with pytest.raises(BusinessRuleError):
        record_movement(material=m, movement_type="SITE_ISSUE", quantity=1)
    with pytest.raises(BusinessRuleError):
        record_movement(material=m, movement_type="PURCHASE_IN", quantity=0)


def test_category_with_materials_cannot_be_deleted(auth_client, cement_cat):
    Material.objects.create(category=cement_cat, name="X")
    client, _ = auth_client(Role.ADMIN)
    assert client.delete(f"/api/v1/material-categories/{cement_cat.id}/").status_code == 400
    cats = client.get("/api/v1/material-categories/").data
    assert cats[0]["material_count"] == 1
