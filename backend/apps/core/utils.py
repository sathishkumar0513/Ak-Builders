"""Indian money, GST and date helpers. All money maths uses Decimal, never float."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


def to_decimal(value) -> Decimal:
    if value is None or value == "":
        return ZERO
    if isinstance(value, float):
        value = str(value)  # avoid binary float artefacts
    return Decimal(value)


def money(value) -> Decimal:
    """Round to paise using commercial rounding (0.005 → 0.01)."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def round_off(value):
    """Round a grand total to the nearest rupee. Returns (rounded_total, round_off_amount)."""
    value = money(value)
    rounded = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return money(rounded), money(rounded - value)


def format_inr(value) -> str:
    """1234567.5 → '₹12,34,567.50' (Indian digit grouping)."""
    value = money(value)
    sign = "-" if value < 0 else ""
    rupees, paise = f"{abs(value):.2f}".split(".")
    if len(rupees) > 3:
        head, tail = rupees[:-3], rupees[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        rupees = ",".join(groups) + "," + tail
    return f"{sign}₹{rupees}.{paise}"


_ONES = [
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two_digits(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three_digits(n: int) -> str:
    hundred, rest = divmod(n, 100)
    parts = []
    if hundred:
        parts.append(_ONES[hundred] + " Hundred")
    if rest:
        parts.append(_two_digits(rest))
    return " ".join(parts)


def _int_to_indian_words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1000)
    if crore:
        parts.append(_int_to_indian_words(crore) + " Crore")
    if lakh:
        parts.append(_two_digits(lakh) + " Lakh")
    if thousand:
        parts.append(_two_digits(thousand) + " Thousand")
    if n:
        parts.append(_three_digits(n))
    return " ".join(parts)


def amount_in_words(value) -> str:
    """125050.75 → 'Rupees One Lakh Twenty Five Thousand Fifty and Seventy Five Paise Only'."""
    value = money(value)
    rupees = int(value)
    paise = int((value - rupees) * 100)
    words = f"Rupees {_int_to_indian_words(rupees)}"
    if paise:
        words += f" and {_two_digits(paise)} Paise"
    return words + " Only"


def financial_year(on: date | None = None, start_month: int = 4) -> str:
    """Indian FY: 11/11/2026 → '2026-27'; 15/02/2027 → '2026-27'."""
    on = on or date.today()
    start = on.year if on.month >= start_month else on.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def is_interstate(company_state_code: str, customer_state_code: str | None) -> bool:
    """Same state → CGST + SGST. Different state → IGST. Unknown → treat as intra-state."""
    if not customer_state_code:
        return False
    return str(company_state_code).zfill(2) != str(customer_state_code).zfill(2)


def split_gst(taxable, gst_rate, interstate: bool) -> dict:
    """Return {'cgst', 'sgst', 'igst'} for one taxable amount."""
    taxable = to_decimal(taxable)
    total_tax = money(taxable * to_decimal(gst_rate) / Decimal("100"))
    if interstate:
        return {"cgst": ZERO, "sgst": ZERO, "igst": total_tax}
    half = money(total_tax / 2)
    return {"cgst": half, "sgst": money(total_tax - half), "igst": ZERO}


INDIAN_STATES = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}
STATE_CHOICES = [(code, name) for code, name in INDIAN_STATES.items()]
