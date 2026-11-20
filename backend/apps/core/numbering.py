from django.db import transaction

from .models import CompanySettings, DocumentSequence
from .utils import financial_year

DEFAULT_PREFIXES = {
    DocumentSequence.DocType.QUOTATION: "AK/QT",
    DocumentSequence.DocType.INVOICE: "AK",
    DocumentSequence.DocType.ADVANCE_RECEIPT: "AK/ADV",
    DocumentSequence.DocType.PAYMENT_RECEIPT: "AK/RCP",
    DocumentSequence.DocType.PURCHASE_ORDER: "AK/PO",
    DocumentSequence.DocType.PROJECT: "AK/PRJ",
    DocumentSequence.DocType.EXPENSE: "AK/EXP",
    DocumentSequence.DocType.REFUND: "AK/REF",
    DocumentSequence.DocType.SUPPLIER_PAYMENT: "AK/SP",
}


def next_document_number(doc_type: str, on=None) -> str:
    """
    Atomically reserve the next number, e.g. next_document_number("INVOICE") → "AK/2026-27/0001".
    Row lock (select_for_update) prevents two users getting the same number.
    """
    start_month = CompanySettings.load().financial_year_start_month
    fy = financial_year(on, start_month)
    with transaction.atomic():
        seq, _ = DocumentSequence.objects.select_for_update().get_or_create(
            doc_type=doc_type,
            financial_year=fy,
            defaults={"prefix": DEFAULT_PREFIXES.get(doc_type, "AK")},
        )
        number = seq.next_number
        seq.next_number = number + 1
        seq.save(update_fields=["next_number"])
    return f"{seq.prefix}/{fy}/{str(number).zfill(seq.padding)}"
