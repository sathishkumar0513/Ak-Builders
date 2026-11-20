"""
Advance and payment logic. Every function is atomic and locks the rows it changes.

Rules enforced here (and by DB CHECK constraints):
- amounts > 0, never more than what is due
- advance: adjusted + refunded ≤ amount
- a bounced cheque stops counting as paid and is debited back to the customer
"""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce

from apps.core.audit import log_action
from apps.core.exceptions import BusinessRuleError
from apps.core.models import AuditLog, DocumentSequence, PaymentMode
from apps.core.numbering import next_document_number
from apps.core.utils import ZERO, money
from apps.invoices.models import Invoice
from apps.invoices.services import recompute_invoice

from . import ledger
from .models import AdvanceAdjustment, AdvancePayment, AdvanceRefund, Payment

AS = AdvancePayment.Status


# ---------------------------------------------------------------------------
# advances
# ---------------------------------------------------------------------------
def recompute_advance(advance):
    adv = AdvancePayment.all_objects.select_for_update().get(pk=advance.pk)
    adv.adjusted_amount = AdvanceAdjustment.objects.filter(advance=adv).aggregate(
        v=Coalesce(Sum("amount"), Value(ZERO))
    )["v"]
    adv.refunded_amount = AdvanceRefund.objects.filter(advance=adv).aggregate(
        v=Coalesce(Sum("amount"), Value(ZERO))
    )["v"]
    if adv.balance > 0:
        adv.status = AS.PARTIAL if adv.adjusted_amount > 0 else AS.OPEN
    else:
        adv.status = AS.REFUNDED if adv.refunded_amount > 0 and adv.adjusted_amount == 0 else AS.ADJUSTED
    adv._skip_audit = True
    adv.save(update_fields=["adjusted_amount", "refunded_amount", "status", "updated_at"])
    return adv


@transaction.atomic
def record_advance(
    *,
    customer,
    amount,
    date,
    mode,
    project=None,
    quotation=None,
    reference_number="",
    cheque_number="",
    cheque_date=None,
    bank_name="",
    notes="",
    received_by=None,
):
    amount = money(amount)
    if amount <= 0:
        raise BusinessRuleError("Amount must be more than zero.", field="amount")
    if project and project.customer_id != customer.pk:
        raise BusinessRuleError("This project belongs to another customer.", field="project")
    if quotation and quotation.customer_id != customer.pk:
        raise BusinessRuleError("This quotation belongs to another customer.", field="quotation")
    if mode == PaymentMode.CHEQUE and not cheque_number:
        raise BusinessRuleError("Enter the cheque number.", field="cheque_number")
    adv = AdvancePayment.objects.create(
        receipt_number=next_document_number(DocumentSequence.DocType.ADVANCE_RECEIPT, date),
        customer=customer,
        project=project,
        quotation=quotation,
        amount=amount,
        date=date,
        mode=mode,
        reference_number=reference_number,
        cheque_number=cheque_number,
        cheque_date=cheque_date,
        bank_name=bank_name,
        notes=notes,
        received_by=received_by,
    )
    ledger.post(
        customer=customer,
        project=project,
        date=date,
        entry_type=ledger.E.ADVANCE,
        credit=amount,
        reference=adv,
        narration=f"Advance {adv.receipt_number} ({adv.get_mode_display()})",
    )
    return adv


@transaction.atomic
def adjust_advance(*, advance, invoice, amount, on=None):
    """Use (part of) an advance to settle an invoice."""
    adv = AdvancePayment.objects.select_for_update().get(pk=advance.pk)
    inv = Invoice.objects.select_for_update().get(pk=invoice.pk)
    amount = money(amount)
    if amount <= 0:
        raise BusinessRuleError("Amount must be more than zero.", field="amount")
    if adv.customer_id != inv.customer_id:
        raise BusinessRuleError("The advance and invoice belong to different customers.")
    if inv.status in (Invoice.Status.CANCELLED, Invoice.Status.PAID):
        raise BusinessRuleError(f"Invoice {inv.number} is {inv.get_status_display().lower()}.")
    if amount > adv.balance:
        raise BusinessRuleError(f"Only ₹{adv.balance} of this advance is left.", field="amount")
    if amount > inv.balance_due:
        raise BusinessRuleError(f"Invoice balance is only ₹{inv.balance_due}.", field="amount")
    adj = AdvanceAdjustment.objects.create(
        advance=adv,
        invoice=inv,
        amount=amount,
        date=on or date.today(),
        notes=f"{adv.receipt_number} → {inv.number}",
    )
    recompute_advance(adv)
    recompute_invoice(inv)
    log_action(
        AuditLog.Action.UPDATE,
        inv,
        changes={"advance_adjusted": [None, f"{amount} from {adv.receipt_number}"]},
    )
    return adj


def auto_adjust_advances(*, invoice):
    """
    Apply the customer's open advances to a new invoice, oldest first:
    advances for the same project first, then advances not tied to any project.
    """
    inv = Invoice.objects.get(pk=invoice.pk)
    candidates = AdvancePayment.objects.filter(customer=inv.customer, status__in=[AS.OPEN, AS.PARTIAL])
    if inv.project_id:
        ordered = list(candidates.filter(project=inv.project).order_by("date", "id")) + list(
            candidates.filter(project__isnull=True).order_by("date", "id")
        )
    else:
        ordered = list(candidates.filter(project__isnull=True).order_by("date", "id"))
    remaining = inv.grand_total - inv.advance_adjusted - inv.amount_paid
    for adv in ordered:
        if remaining <= 0:
            break
        use = min(adv.balance, remaining)
        if use > 0:
            adjust_advance(advance=adv, invoice=inv, amount=use, on=inv.invoice_date)
            remaining -= use


@transaction.atomic
def remove_adjustment(*, adjustment):
    inv, adv = adjustment.invoice, adjustment.advance
    if inv.status == Invoice.Status.CANCELLED:
        raise BusinessRuleError("The invoice is cancelled.")
    adjustment.delete()
    recompute_advance(adv)
    recompute_invoice(inv)


@transaction.atomic
def refund_advance(*, advance, amount, date, mode, reason, reference_number=""):
    adv = AdvancePayment.objects.select_for_update().get(pk=advance.pk)
    amount = money(amount)
    if amount <= 0:
        raise BusinessRuleError("Amount must be more than zero.", field="amount")
    if amount > adv.balance:
        raise BusinessRuleError(
            f"Only ₹{adv.balance} of this advance is unused and can be refunded.", field="amount"
        )
    if not reason:
        raise BusinessRuleError("Enter the reason for the refund.", field="reason")
    if date < adv.date:
        raise BusinessRuleError(
            f"Refund date can't be before the advance date ({adv.date:%d/%m/%Y}).", field="date"
        )
    refund = AdvanceRefund.objects.create(
        refund_number=next_document_number(DocumentSequence.DocType.REFUND, date),
        advance=adv,
        amount=amount,
        date=date,
        mode=mode,
        reference_number=reference_number,
        reason=reason,
    )
    recompute_advance(adv)
    ledger.post(
        customer=adv.customer,
        project=adv.project,
        date=date,
        entry_type=ledger.E.REFUND,
        debit=amount,
        reference=refund,
        narration=f"Refund of {adv.receipt_number}: {reason}",
    )
    return refund


@transaction.atomic
def cancel_advance(*, advance, reason):
    adv = AdvancePayment.objects.select_for_update().get(pk=advance.pk)
    if adv.adjusted_amount > 0 or adv.refunded_amount > 0:
        raise BusinessRuleError("This advance is already adjusted or refunded. Remove those first.")
    adv.soft_delete()
    ledger.reverse(
        reference=adv, date=date.today(), narration=f"Advance {adv.receipt_number} cancelled: {reason}"
    )
    log_action(AuditLog.Action.DELETE, adv, changes={"reason": [None, reason]})


# ---------------------------------------------------------------------------
# payments
# ---------------------------------------------------------------------------
@transaction.atomic
def record_payment(
    *,
    customer,
    amount,
    date,
    mode,
    invoice=None,
    payment_stage=None,
    project=None,
    reference_number="",
    cheque_number="",
    cheque_date=None,
    bank_name="",
    notes="",
    received_by=None,
):
    """
    A payment must settle something: an invoice, or a project payment stage that has not been invoiced yet.
    Money received with nothing to settle is recorded as an Advance instead.
    """
    amount = money(amount)
    if amount <= 0:
        raise BusinessRuleError("Amount must be more than zero.", field="amount")
    if invoice is None and payment_stage is None:
        raise BusinessRuleError(
            "Choose the invoice or project stage this payment is for. "
            "Money received in advance should be recorded as an Advance.",
            field="invoice",
        )
    if mode == PaymentMode.CHEQUE and not cheque_number:
        raise BusinessRuleError("Enter the cheque number.", field="cheque_number")

    if invoice is not None:
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if invoice.customer_id != customer.pk:
            raise BusinessRuleError("This invoice belongs to another customer.", field="invoice")
        if invoice.status in (Invoice.Status.CANCELLED, Invoice.Status.PAID):
            raise BusinessRuleError(
                f"Invoice {invoice.number} is {invoice.get_status_display().lower()}.", field="invoice"
            )
        if amount > invoice.balance_due:
            raise BusinessRuleError(
                f"Amount is more than the balance due on {invoice.number} (₹{invoice.balance_due}).",
                field="amount",
            )
        if date < invoice.invoice_date:
            raise BusinessRuleError(
                f"Payment date can't be before the invoice date ({invoice.invoice_date:%d/%m/%Y}).",
                field="date",
            )
        project = invoice.project or project
        payment_stage = invoice.payment_stage or payment_stage
    else:
        from apps.projects.models import PaymentStage

        payment_stage = (
            PaymentStage.objects.select_for_update().select_related("project").get(pk=payment_stage.pk)
        )
        project = payment_stage.project
        if project.customer_id != customer.pk:
            raise BusinessRuleError("This project belongs to another customer.", field="payment_stage")
        if payment_stage.invoices.exclude(status=Invoice.Status.CANCELLED).exists():
            raise BusinessRuleError(
                "This stage is already invoiced — record the payment against the invoice.",
                field="payment_stage",
            )
        remaining = payment_stage.amount - payment_stage.amount_received
        if amount > remaining:
            raise BusinessRuleError(
                f"Amount is more than what is left on this stage (₹{remaining}).", field="amount"
            )

    payment = Payment.objects.create(
        receipt_number=next_document_number(DocumentSequence.DocType.PAYMENT_RECEIPT, date),
        customer=customer,
        project=project,
        invoice=invoice,
        payment_stage=payment_stage,
        date=date,
        amount=amount,
        mode=mode,
        reference_number=reference_number,
        cheque_number=cheque_number,
        cheque_date=cheque_date,
        bank_name=bank_name,
        cheque_status=Payment.ChequeStatus.PENDING if mode == PaymentMode.CHEQUE else Payment.ChequeStatus.NA,
        notes=notes,
        received_by=received_by,
    )
    against = invoice.number if invoice else payment_stage.name
    ledger.post(
        customer=customer,
        project=project,
        date=date,
        entry_type=ledger.E.PAYMENT,
        credit=amount,
        reference=payment,
        narration=f"Receipt {payment.receipt_number} ({payment.get_mode_display()}) for {against}",
    )
    _after_payment_change(payment)
    return payment


def _after_payment_change(payment):
    if payment.invoice_id:
        recompute_invoice(Invoice.objects.select_for_update().get(pk=payment.invoice_id))
    elif payment.payment_stage_id:
        from apps.projects.services import recompute_stage

        recompute_stage(payment.payment_stage)


@transaction.atomic
def cancel_payment(*, payment, reason):
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if not reason:
        raise BusinessRuleError("Enter a reason for cancelling.", field="reason")
    payment.soft_delete()
    if payment.cheque_status != Payment.ChequeStatus.BOUNCED:  # a bounce already undid the credit
        ledger.reverse(
            reference=payment,
            date=date.today(),
            narration=f"Receipt {payment.receipt_number} cancelled: {reason}",
        )
    log_action(AuditLog.Action.DELETE, payment, changes={"reason": [None, reason]})
    _after_payment_change(payment)


@transaction.atomic
def set_cheque_status(*, payment, status, on=None, charges=Decimal("0")):
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    CS = Payment.ChequeStatus
    if payment.mode != PaymentMode.CHEQUE:
        raise BusinessRuleError("This payment is not a cheque.")
    if payment.cheque_status != CS.PENDING:
        raise BusinessRuleError(f"Cheque is already {payment.get_cheque_status_display().lower()}.")
    payment.cheque_status = status
    payment.save(update_fields=["cheque_status", "updated_at"])
    if status == CS.BOUNCED:
        ledger.post(
            customer=payment.customer,
            project=payment.project,
            date=on or date.today(),
            entry_type=ledger.E.CHEQUE_BOUNCE,
            debit=payment.amount,
            reference=payment,
            narration=f"Cheque {payment.cheque_number} bounced ({payment.receipt_number})",
        )
        _after_payment_change(payment)
    return payment
