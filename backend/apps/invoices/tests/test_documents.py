from datetime import date

import pytest
from django.core import mail

from apps.accounts.models import Role
from apps.customers.models import Customer
from apps.payments.models import PaymentReminder

pytestmark = pytest.mark.django_db


@pytest.fixture
def invoice(auth_client):
    client, _ = auth_client(Role.ACCOUNTANT)
    c = Customer.objects.create(name="Ravi Kumar", phone="9876500001", email="ravi@example.com")
    inv = client.post(
        "/api/v1/invoices/",
        {
            "customer": c.id,
            "invoice_date": date.today().isoformat(),
            "items": [
                {
                    "description": "Tiling labour",
                    "item_type": "SERVICE",
                    "quantity": "10",
                    "rate": "500",
                    "gst_rate": "18",
                    "unit": "sqft",
                }
            ],
        },
        format="json",
    )
    assert inv.status_code == 201, inv.data
    return client, inv.data


def test_invoice_pdf_share_reminder_and_email(invoice):
    client, inv = invoice
    base = f"/api/v1/invoices/{inv['id']}/"
    pdf = client.get(base + "pdf/?download=1")
    assert (
        pdf.status_code == 200
        and pdf.content.startswith(b"%PDF")
        and "attachment" in pdf["Content-Disposition"]
    )

    share = client.get(base + "share-text/").data
    assert inv["number"] in share["message"] and share["phone"] == "9876500001"
    reminder = client.get(base + "share-text/?reminder=1").data["message"]
    assert reminder != share["message"] and "5,900" in reminder

    assert client.post(base + "log-reminder/", {"channel": "WHATSAPP"}, format="json").status_code == 200
    assert (
        client.post(base + "log-reminder/", {"channel": "PIGEON-POST-XL"}, format="json").status_code == 400
    )
    assert PaymentReminder.objects.filter(invoice_id=inv["id"]).count() == 1

    r = client.post(
        base + "email/", {"to": ["ravi@example.com"], "message": "Please find the invoice."}, format="json"
    )
    assert r.status_code == 200
    assert len(mail.outbox) == 1 and mail.outbox[0].attachments[0][0].endswith(".pdf")
    assert client.post(base + "email/", {"to": ["not-an-email"]}, format="json").status_code == 400
