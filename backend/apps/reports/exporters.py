"""Turn any report (see services.py for the shape) into an .xlsx or a PDF."""

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.models import CompanySettings
from apps.core.pdf import BRAND, BRAND_LIGHT, GREY, LINE, _esc, _register_fonts, _styles
from apps.core.utils import format_inr

NUMERIC = ("money", "qty", "number", "percent")
XL_FORMATS = {
    "money": "#,##0.00",
    "qty": "#,##0.###",
    "number": "0",
    "percent": '0.0"%"',
    "date": "DD-MM-YYYY",
}


def fmt(value, type_):
    """Text for PDF cells / KPI tiles."""
    if value is None or value == "":
        return ""
    if type_ == "money":
        return format_inr(value)
    if type_ == "qty":
        v = Decimal(value).normalize()
        return f"{v:f}"
    if type_ == "percent":
        return f"{Decimal(value):.1f}%"
    if type_ == "date" and isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def filename(report, ext):
    return f"{report['key']}_{report['date_from']:%Y%m%d}-{report['date_to']:%Y%m%d}.{ext}"


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------
def to_xlsx(report):
    company = CompanySettings.load()
    wb = Workbook()
    ws = wb.active
    ws.title = report["title"][:31].replace("/", "-")
    cols = report["columns"]
    n = len(cols)
    last = get_column_letter(n)
    thin = Side(style="thin", color="CBD5E1")

    ws.append([company.name])
    ws["A1"].font = Font(bold=True, size=14, color="EA580C")
    ws.append([report["title"]])
    ws["A2"].font = Font(bold=True, size=12)
    ws.append([report.get("subtitle", "")])
    ws["A3"].font = Font(italic=True, color="64748B")
    ws.append([f"Generated {timezone.localtime():%d/%m/%Y %H:%M}"])
    ws["A4"].font = Font(color="64748B", size=9)
    for r in range(1, 5):
        ws.merge_cells(f"A{r}:{last}{r}")

    row = 6
    if report.get("summary"):  # KPI pairs: label row + value row
        for i, k in enumerate(report["summary"][:n]):
            c = ws.cell(row=row, column=i + 1, value=k["label"])
            c.font = Font(size=9, color="64748B")
            v = ws.cell(row=row + 1, column=i + 1, value=_xl(k["value"], k.get("type")))
            v.font = Font(bold=True)
            if k.get("type") in XL_FORMATS:
                v.number_format = XL_FORMATS[k["type"]]
        row += 3

    header_row = row
    for i, c in enumerate(cols, start=1):
        cell = ws.cell(row=row, column=i, value=c["label"])
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="EA580C")
        cell.alignment = Alignment(
            horizontal="right" if c["type"] in NUMERIC else "left", vertical="center", wrap_text=True
        )
    widths = [max(len(c["label"]), 8) for c in cols]
    for r in report["rows"]:
        row += 1
        for i, c in enumerate(cols, start=1):
            v = _xl(r.get(c["key"]), c["type"])
            cell = ws.cell(row=row, column=i, value=v)
            if c["type"] in XL_FORMATS and v is not None:
                cell.number_format = XL_FORMATS[c["type"]]
            if r.get("_bold"):
                cell.font = Font(bold=True)
            cell.border = Border(bottom=thin)
            widths[i - 1] = max(widths[i - 1], min(len(fmt(r.get(c["key"]), c["type"])), 45))
    if report.get("totals"):
        row += 1
        ws.cell(row=row, column=1, value="Total").font = Font(bold=True)
        for i, c in enumerate(cols, start=1):
            if c["key"] in report["totals"] and i > 1:
                cell = ws.cell(row=row, column=i, value=_xl(report["totals"][c["key"]], c["type"]))
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor="FFF7ED")
                if c["type"] in XL_FORMATS:
                    cell.number_format = XL_FORMATS[c["type"]]
        ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor="FFF7ED")

    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w + 3
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    if report["rows"]:
        ws.auto_filter.ref = f"A{header_row}:{last}{header_row + len(report['rows'])}"
    ws.page_setup.orientation = "landscape" if n > 6 else "portrait"
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{header_row}:{header_row}"

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _xl(value, type_):
    """Excel-safe value. Text that looks like a formula (e.g. a customer named '=HYPERLINK(…)')
    is prefixed with an apostrophe so Excel shows it as text instead of running it."""
    if value is None:
        return None
    if type_ in ("money", "qty", "percent"):
        return float(value)  # Excel stores numbers as floats; values are already rounded Decimals
    if type_ == "number":
        return int(value)
    if isinstance(value, (date, datetime)):
        return value
    text = str(value)
    return "'" + text if text.startswith(FORMULA_START) else text


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def to_pdf(report):
    _register_fonts()
    st = _styles()
    company = CompanySettings.load()
    cols = report["columns"]
    page = landscape(A4) if len(cols) > 6 else A4
    width = page[0] - 24 * mm

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=page,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=16 * mm,
        title=report["title"],
        author=company.name,
    )
    generated = f"{company.name} · {report['title']} · generated {timezone.localtime():%d/%m/%Y %H:%M}"

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("DejaVu", 7)
        canvas.setFillColor(GREY)
        canvas.drawString(12 * mm, 8 * mm, generated)
        canvas.drawRightString(page[0] - 12 * mm, 8 * mm, f"Page {d.page}")
        canvas.restoreState()

    story = [
        Table(
            [
                [Paragraph(_esc(company.name), st["company"]), Paragraph(_esc(report["title"]), st["title"])],
                [
                    Paragraph(_esc(", ".join(x for x in [company.address, company.city] if x)), st["small"]),
                    Paragraph(_esc(report.get("subtitle", "")), st["right"]),
                ],
            ],
            colWidths=[width * 0.5, width * 0.5],
            style=[
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, -1), (-1, -1), 1, BRAND),
            ],
        ),
        Spacer(1, 4 * mm),
    ]

    if report.get("summary"):
        kp = report["summary"][:6]
        cells = [
            [
                Paragraph(
                    f"<font color='#64748b' size='7'>{_esc(k['label'])}</font><br/>"
                    f"<b>{_esc(fmt(k['value'], k.get('type', 'money')))}</b>",
                    st["base"],
                )
                for k in kp
            ]
        ]
        story += [
            Table(
                cells,
                colWidths=[width / len(kp)] * len(kp),
                style=[
                    ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ],
            ),
            Spacer(1, 4 * mm),
        ]

    widths = _pdf_widths(report, width)
    small = len(cols) > 10
    cell_style = ParagraphStyle(
        "c", parent=st["cell"], fontSize=7 if small else 8, leading=8.5 if small else 10
    )
    cell_r = ParagraphStyle("cr", parent=cell_style, alignment=TA_RIGHT)

    def cell(v, c, bold=False):
        style = cell_r if c["type"] in NUMERIC else cell_style
        text = _esc(fmt(v, c["type"]))
        return Paragraph(f"<b>{text}</b>" if bold else text, style)

    data = [[Paragraph(_esc(c["label"]), st["th_r"] if c["type"] in NUMERIC else st["th"]) for c in cols]]
    bold_rows = []
    for r in report["rows"]:
        if r.get("_bold"):
            bold_rows.append(len(data))
        data.append([cell(r.get(c["key"]), c, r.get("_bold")) for c in cols])
    if not report["rows"]:
        data.append([Paragraph("No records for these filters.", st["small"])] + [""] * (len(cols) - 1))
    if report.get("totals"):
        totals = report["totals"]
        data.append(
            [Paragraph("<b>Total</b>", st["cell"])]
            + [cell(totals.get(c["key"]), c, True) if c["key"] in totals else "" for c in cols[1:]]
        )
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    if report.get("totals"):
        style += [("BACKGROUND", (0, -1), (-1, -1), BRAND_LIGHT), ("LINEABOVE", (0, -1), (-1, -1), 1, BRAND)]
    if not report["rows"]:
        style.append(("SPAN", (0, 1), (-1, 1)))
    story.append(LongTable(data, colWidths=widths, repeatRows=1, style=TableStyle(style)))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def _pdf_widths(report, width):
    """Measured with the real font: numbers and dates never wrap; text columns share the rest."""
    cols = report["columns"]
    size = _font_size(cols)
    natural = []
    for c in cols:
        values = [fmt(r.get(c["key"]), c["type"]) for r in report["rows"]]
        texts = [stringWidth(v[:45], "DejaVu", size) for v in values]
        if report.get("totals") and c["key"] in report["totals"]:
            texts.append(stringWidth(fmt(report["totals"][c["key"]], c["type"]), "DejaVu-Bold", size))
        label = max(stringWidth(w, "DejaVu-Bold", 7.5) for w in c["label"].split())  # labels may wrap
        natural.append(max(texts + [label, 20]) + 8)
    rigid = [c["type"] in NUMERIC or c["type"] == "date" for c in cols]
    fixed = sum(w for w, r in zip(natural, rigid) if r)
    flex = sum(w for w, r in zip(natural, rigid) if not r)
    if fixed + flex <= width:  # everything fits: stretch to the page width
        k = width / (fixed + flex)
        return [w * k for w in natural]
    n_text = sum(1 for r in rigid if not r) or 1
    min_text = 22 * mm * n_text
    room = width - fixed
    if room >= min_text:  # text columns wrap into what is left
        k = room / flex if flex else 1
        return [w if r else w * k for w, r in zip(natural, rigid)]
    # very wide: text columns get their minimum, numbers share the rest (they may shrink a little)
    k = (width - min_text) / fixed
    return [w * k if r else 22 * mm for w, r in zip(natural, rigid)]


def _font_size(cols):
    return 7 if len(cols) > 10 else 8
