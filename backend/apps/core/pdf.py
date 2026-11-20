"""
A4 PDF renderer for GST documents (quotation now; invoice and receipts in Phase 5).
ReportLab only — no system libraries, so it works on Windows, Linux and inside Docker.
Uses the bundled DejaVu Sans font for the ₹ symbol.
"""

from io import BytesIO
from pathlib import Path

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .utils import format_inr

FONT_DIR = Path(settings.BASE_DIR) / "assets" / "fonts"
BRAND = colors.HexColor("#ea580c")
BRAND_LIGHT = colors.HexColor("#fff7ed")
GREY = colors.HexColor("#64748b")
LINE = colors.HexColor("#cbd5e1")
DARK = colors.HexColor("#0f172a")

_fonts_ready = False


def _register_fonts():
    global _fonts_ready
    if _fonts_ready:
        return
    pdfmetrics.registerFont(TTFont("DejaVu", str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(
        "DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu", boldItalic="DejaVu-Bold"
    )
    _fonts_ready = True


def _styles():
    base = ParagraphStyle("base", fontName="DejaVu", fontSize=8.5, leading=11, textColor=DARK)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=7.5, leading=9.5, textColor=GREY),
        "company": ParagraphStyle("company", parent=base, fontName="DejaVu-Bold", fontSize=16, leading=19),
        "title": ParagraphStyle(
            "title",
            parent=base,
            fontName="DejaVu-Bold",
            fontSize=15,
            leading=18,
            textColor=BRAND,
            alignment=TA_RIGHT,
        ),
        "right": ParagraphStyle("right", parent=base, alignment=TA_RIGHT),
        "h": ParagraphStyle(
            "h", parent=base, fontName="DejaVu-Bold", fontSize=8, textColor=GREY, spaceAfter=2
        ),
        "bold": ParagraphStyle("bold", parent=base, fontName="DejaVu-Bold"),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8, leading=10),
        "cell_r": ParagraphStyle("cell_r", parent=base, fontSize=8, leading=10, alignment=TA_RIGHT),
        "th": ParagraphStyle(
            "th", parent=base, fontName="DejaVu-Bold", fontSize=7.5, leading=9, textColor=colors.white
        ),
        "th_r": ParagraphStyle(
            "th_r",
            parent=base,
            fontName="DejaVu-Bold",
            fontSize=7.5,
            leading=9,
            textColor=colors.white,
            alignment=TA_RIGHT,
        ),
    }


def _esc(text):
    return (
        (str(text or ""))
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _qty(q):
    q = q.normalize()
    return f"{q:f}"


def _logo_flowable(company, max_w=22 * mm, max_h=22 * mm):
    """Logo scaled to fit, or None. A missing / corrupt logo file must never break a PDF."""
    if not company.logo:
        return None
    try:
        # Read through the storage, not .path: works for local disk and for Cloudinary
        with company.logo.open("rb") as f:
            data = f.read()
        if not data:
            return None
        iw, ih = ImageReader(BytesIO(data)).getSize()
        scale = min(max_w / iw, max_h / ih)
        return Image(BytesIO(data), width=iw * scale, height=ih * scale)
    except Exception:
        return None


def _footer(canvas, doc):
    canvas.saveState()
    stamp = getattr(doc, "stamp_text", None)
    if stamp:  # CANCELLED / PAID watermark
        canvas.setFont("DejaVu-Bold", 60)
        red = stamp in ("CANCELLED", "BOUNCED")
        canvas.setFillColor(
            colors.Color(0.86, 0.15, 0.15, alpha=0.16) if red else colors.Color(0.09, 0.64, 0.29, alpha=0.16)
        )
        canvas.translate(A4[0] / 2, A4[1] / 2)
        canvas.rotate(35)
        canvas.drawCentredString(0, 0, stamp)
        canvas.restoreState()
        canvas.saveState()
    canvas.setFont("DejaVu", 7)
    canvas.setFillColor(GREY)
    canvas.drawString(15 * mm, 9 * mm, getattr(doc, "footer_text", ""))
    canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def render_gst_document(
    *,
    company,
    title,
    meta,
    party_title,
    party_lines,
    extra_box=None,
    items,
    doc,
    gst_summary=None,
    terms="",
    notes="",
    show_bank=True,
    footer_text="",
    settlement_rows=None,
    stamp=None,
):
    """
    meta: [(label, value)] shown under the title (No., Date, Valid until…)
    party_lines: list of strings (name first) for the "Bill to / Quotation for" box
    extra_box: (title, [lines]) for the second box (site / place of supply)
    items: QuotationItem / InvoiceItem objects
    doc: object with subtotal, discount_total, taxable_amount, cgst/sgst/igst_amount, round_off,
         grand_total, amount_in_words, is_interstate
    """
    _register_fonts()
    st = _styles()
    buf = BytesIO()
    pdf = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=16 * mm,
        title=f"{title} {meta[0][1] if meta else ''}",
        author=company.name,
    )
    pdf.footer_text = footer_text
    W = A4[0] - 30 * mm
    story = []

    # --- header: logo + company | document title + meta
    left = []
    logo = _logo_flowable(company)
    if logo:
        left.append(logo)
    addr = ", ".join(
        filter(None, [company.address, company.city, f"{company.state} {company.pincode}".strip()])
    )
    contact = " · ".join(filter(None, [company.phone, company.email, company.website]))
    company_block = [Paragraph(_esc(company.name), st["company"])]
    if company.tagline:
        company_block.append(Paragraph(_esc(company.tagline), st["small"]))
    company_block += [Paragraph(_esc(addr), st["base"]), Paragraph(_esc(contact), st["base"])]
    if company.gstin:
        company_block.append(
            Paragraph(
                f"<b>GSTIN:</b> {_esc(company.gstin)}"
                + (f" &nbsp; <b>PAN:</b> {_esc(company.pan)}" if company.pan else ""),
                st["base"],
            )
        )
    meta_rows = [
        [Paragraph(_esc(k), st["small"]), Paragraph(f"<b>{_esc(v)}</b>", st["right"])] for k, v in meta
    ]
    meta_tbl = Table(meta_rows, colWidths=[25 * mm, 43 * mm])
    meta_tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    right = [Paragraph(_esc(title.upper()), st["title"]), Spacer(1, 2 * mm), meta_tbl]
    right_w = 68 * mm
    logo_w = 25 * mm if left else 0
    header = Table([[left or "", company_block, right]], colWidths=[logo_w, W - logo_w - right_w, right_w])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story += [header, Spacer(1, 3 * mm)]
    story.append(
        Table([[""]], colWidths=[W], rowHeights=[1.2], style=[("BACKGROUND", (0, 0), (-1, -1), BRAND)])
    )
    story.append(Spacer(1, 3 * mm))

    # --- party boxes
    def box(heading, lines):
        content = [Paragraph(_esc(heading), st["h"])]
        for i, line in enumerate(lines):
            if line:
                content.append(Paragraph(_esc(line) if i else f"<b>{_esc(line)}</b>", st["base"]))
        return content

    boxes = [[box(party_title, party_lines), box(*extra_box) if extra_box else ""]]
    party_tbl = Table(boxes, colWidths=[W / 2, W / 2])
    party_style = [
        ("BOX", (0, 0), (0, 0), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if extra_box:
        party_style.append(("BOX", (1, 0), (1, 0), 0.6, LINE))
    party_tbl.setStyle(TableStyle(party_style))
    story += [party_tbl, Spacer(1, 4 * mm)]

    # --- items
    tax_head = "IGST" if doc.is_interstate else "GST"
    head = ["#", "Description", "HSN/SAC", "Qty", "Rate", "Disc", "Taxable", tax_head, "Amount"]
    rows = [[Paragraph(h, st["th_r"] if i >= 3 else st["th"]) for i, h in enumerate(head)]]
    for n, it in enumerate(items, 1):
        tax = it.cgst_amount + it.sgst_amount + it.igst_amount
        disc = f"{it.discount_percent.normalize():f}%" if it.discount_percent else "—"
        rows.append(
            [
                Paragraph(str(n), st["cell"]),
                Paragraph(_esc(it.description), st["cell"]),
                Paragraph(_esc(it.hsn_code), st["cell"]),
                Paragraph(f"{_qty(it.quantity)} {_esc(it.get_unit_display())}", st["cell_r"]),
                Paragraph(format_inr(it.rate), st["cell_r"]),
                Paragraph(disc, st["cell_r"]),
                Paragraph(format_inr(it.taxable_amount), st["cell_r"]),
                Paragraph(
                    f"{format_inr(tax)}<br/>"
                    f"<font size=6.5 color='#64748b'>{it.gst_rate.normalize():f}%</font>",
                    st["cell_r"],
                ),
                Paragraph(format_inr(it.line_total), st["cell_r"]),
            ]
        )
    cw = [7 * mm, None, 17 * mm, 18 * mm, 20 * mm, 11 * mm, 22 * mm, 19 * mm, 23 * mm]
    cw[1] = W - sum(c for c in cw if c)
    items_tbl = Table(rows, colWidths=cw, repeatRows=1)
    items_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story += [items_tbl, Spacer(1, 3 * mm)]

    # --- totals (right) + amount in words & GST summary (left)
    tot = [("Subtotal", format_inr(doc.subtotal))]
    if doc.discount_total:
        tot.append(("Discount", f"− {format_inr(doc.discount_total)}"))
    tot.append(("Taxable value", format_inr(doc.taxable_amount)))
    if doc.is_interstate:
        tot.append(("IGST", format_inr(doc.igst_amount)))
    else:
        tot += [("CGST", format_inr(doc.cgst_amount)), ("SGST", format_inr(doc.sgst_amount))]
    extra = getattr(doc, "extra_charges_display", None)
    if extra:
        tot.append(extra)
    if doc.round_off:
        tot.append(("Round off", f"{'+' if doc.round_off > 0 else '−'} {format_inr(abs(doc.round_off))}"))
    tot_rows = [[Paragraph(k, st["base"]), Paragraph(v, st["right"])] for k, v in tot]
    tot_rows.append(
        [
            Paragraph("<b>Grand total</b>", st["bold"]),
            Paragraph(
                f"<b>{format_inr(doc.grand_total)}</b>",
                ParagraphStyle("gt", parent=st["right"], fontSize=11, fontName="DejaVu-Bold"),
            ),
        ]
    )
    gt_row = len(tot_rows) - 1
    for k, v in settlement_rows or []:  # e.g. advance adjusted, paid, balance due (invoices)
        tot_rows.append([Paragraph(_esc(k), st["base"]), Paragraph(_esc(v), st["right"])])
    tot_tbl = Table(tot_rows, colWidths=[38 * mm, 32 * mm])
    tot_style = [
        ("LINEABOVE", (0, gt_row), (-1, gt_row), 0.8, DARK),
        ("BACKGROUND", (0, gt_row), (-1, gt_row), BRAND_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if settlement_rows:
        tot_style += [
            ("LINEABOVE", (0, -1), (-1, -1), 0.6, DARK),
            ("FONTNAME", (0, -1), (-1, -1), "DejaVu-Bold"),
        ]
    tot_tbl.setStyle(TableStyle(tot_style))

    left_col = [
        Paragraph("Amount in words", st["h"]),
        Paragraph(f"<b>{_esc(doc.amount_in_words)}</b>", st["base"]),
    ]
    if gst_summary:
        left_col.append(Spacer(1, 3 * mm))
        gh = ["GST %", "Taxable", "IGST"] if doc.is_interstate else ["GST %", "Taxable", "CGST", "SGST"]
        g_rows = [[Paragraph(h, st["small"]) for h in gh]]
        for g in gst_summary:
            r = [f"{g['rate'].normalize():f}%", format_inr(g["taxable"])]
            r += (
                [format_inr(g["igst"])]
                if doc.is_interstate
                else [format_inr(g["cgst"]), format_inr(g["sgst"])]
            )
            g_rows.append([Paragraph(x, st["small"]) for x in r])
        g_tbl = Table(g_rows, colWidths=[14 * mm] + [24 * mm] * (len(gh) - 1))
        g_tbl.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.3, LINE),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )
        left_col.append(g_tbl)
    sum_tbl = Table([[left_col, tot_tbl]], colWidths=[W - 72 * mm, 72 * mm])
    sum_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [KeepTogether(sum_tbl), Spacer(1, 4 * mm)]

    # --- notes, terms, bank, signature
    if notes:
        story += [Paragraph("Notes", st["h"]), Paragraph(_esc(notes), st["base"]), Spacer(1, 3 * mm)]
    bottom_left = []
    if terms:
        bottom_left += [Paragraph("Terms &amp; conditions", st["h"]), Paragraph(_esc(terms), st["small"])]
    if show_bank and (company.bank_account_number or company.upi_id):
        bank = [
            f"<b>{_esc(company.bank_account_name or company.name)}</b>",
            " · ".join(filter(None, [company.bank_name, company.bank_branch])),
            (
                f"A/c {_esc(company.bank_account_number)} · IFSC {_esc(company.bank_ifsc)}"
                if company.bank_account_number
                else ""
            ),
            f"UPI: {_esc(company.upi_id)}" if company.upi_id else "",
        ]
        bottom_left += [
            Spacer(1, 2 * mm),
            Paragraph("Bank details", st["h"]),
            Paragraph("<br/>".join(b for b in bank if b), st["base"]),
        ]
    sign = [
        Spacer(1, 2 * mm),
        Paragraph(f"For <b>{_esc(company.name)}</b>", st["right"]),
        Spacer(1, 14 * mm),
        Paragraph("Authorised signatory", ParagraphStyle("sig", parent=st["small"], alignment=TA_RIGHT)),
    ]
    end_tbl = Table([[bottom_left or "", sign]], colWidths=[W - 60 * mm, 60 * mm])
    end_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(KeepTogether(end_tbl))

    if stamp:
        pdf.stamp_text = stamp
    pdf.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def render_receipt(
    *,
    company,
    title,
    number,
    on,
    party_title,
    party_lines,
    rows,
    amount,
    amount_words,
    notes="",
    footer_text="",
    stamp=None,
):
    """Receipt layout (advance receipt, payment receipt, refund voucher)."""
    _register_fonts()
    st = _styles()
    buf = BytesIO()
    pdf = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=16 * mm,
        title=f"{title} {number}",
        author=company.name,
    )
    pdf.footer_text = footer_text
    if stamp:
        pdf.stamp_text = stamp
    W = A4[0] - 30 * mm
    logo = _logo_flowable(company, 18 * mm, 18 * mm)
    addr = ", ".join(
        filter(None, [company.address, company.city, f"{company.state} {company.pincode}".strip()])
    )
    block = [
        Paragraph(_esc(company.name), st["company"]),
        Paragraph(_esc(addr), st["base"]),
        Paragraph(_esc(" · ".join(filter(None, [company.phone, company.email]))), st["base"]),
    ]
    if company.gstin:
        block.append(Paragraph(f"<b>GSTIN:</b> {_esc(company.gstin)}", st["base"]))
    right = [
        Paragraph(_esc(title.upper()), st["title"]),
        Spacer(1, 2 * mm),
        Paragraph(f"No. <b>{_esc(number)}</b>", st["right"]),
        Paragraph(f"Date <b>{on:%d/%m/%Y}</b>", st["right"]),
    ]
    lw = 21 * mm if logo else 0
    head = Table([[logo or "", block, right]], colWidths=[lw, W - lw - 66 * mm, 66 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story = [
        head,
        Spacer(1, 3 * mm),
        Table([[""]], colWidths=[W], rowHeights=[1.2], style=[("BACKGROUND", (0, 0), (-1, -1), BRAND)]),
        Spacer(1, 4 * mm),
    ]
    party = [Paragraph(_esc(party_title), st["h"])]
    party += [
        Paragraph(_esc(x) if i else f"<b>{_esc(x)}</b>", st["base"]) for i, x in enumerate(party_lines) if x
    ]
    big = ParagraphStyle(
        "amt", parent=st["base"], fontSize=18, leading=22, fontName="DejaVu-Bold", textColor=BRAND
    )
    amt_box = [
        Paragraph("Amount", st["h"]),
        Paragraph(f"<b>{format_inr(amount)}</b>", big),
        Paragraph(_esc(amount_words), st["small"]),
    ]
    top = Table([[party, amt_box]], colWidths=[W * 0.55, W * 0.45])
    top.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (0, 0), 0.6, LINE),
                ("BOX", (1, 0), (1, 0), 0.6, LINE),
                ("BACKGROUND", (1, 0), (1, 0), BRAND_LIGHT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story += [top, Spacer(1, 4 * mm)]
    detail = Table(
        [[Paragraph(_esc(k), st["small"]), Paragraph(_esc(v), st["base"])] for k, v in rows if v],
        colWidths=[45 * mm, W - 45 * mm],
    )
    detail.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story += [detail, Spacer(1, 4 * mm)]
    if notes:
        story += [Paragraph("Notes", st["h"]), Paragraph(_esc(notes), st["base"]), Spacer(1, 3 * mm)]
    story += [
        Spacer(1, 8 * mm),
        Paragraph(f"For <b>{_esc(company.name)}</b>", st["right"]),
        Spacer(1, 14 * mm),
        Paragraph("Authorised signatory", ParagraphStyle("sig", parent=st["small"], alignment=TA_RIGHT)),
    ]
    pdf.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
