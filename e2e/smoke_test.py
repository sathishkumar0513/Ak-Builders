"""
Read-only browser smoke test: logs in and opens every page the user's role can see
(desktop and phone sizes), failing on JavaScript errors, failed API calls (5xx) or an
error screen. It never clicks Save / Delete, so it is safe to run against real data.

One-time setup:
    pip install playwright
    python -m playwright install chromium

Run (app must be running, e.g. via scripts\\run_dev.bat):
    python e2e/smoke_test.py --user admin --password "your password"
    python e2e/smoke_test.py --url http://192.168.1.20:5173 --user murugan --password "..."
"""

import argparse
import re
import sys

from playwright.sync_api import sync_playwright

PAGES = [
    "/", "/customers", "/materials", "/suppliers", "/purchases", "/quotations", "/projects",
    "/advances", "/payments", "/invoices", "/expenses", "/reports", "/users", "/audit-log",
    "/settings", "/profile",
    "/reports/payments", "/reports/outstanding", "/reports/customer-outstanding",
    "/reports/sales-register", "/reports/quotations", "/reports/project-pl", "/reports/expenses",
    "/reports/stock", "/reports/purchases",
]
DETAIL_LISTS = ["/customers", "/materials", "/quotations", "/projects", "/invoices", "/advances",
                "/purchases", "/suppliers"]
ERROR_TEXT = re.compile(r"Something went wrong|Illegal constructor|is not defined|Cannot read properties")


def run(url, user, password, headed):
    problems, checked = [], 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        for label, viewport in (("desktop", {"width": 1366, "height": 900}), ("phone", {"width": 390, "height": 844})):
            page = browser.new_context(viewport=viewport).new_page()
            page.on("pageerror", lambda e, lb=label: problems.append(f"[{lb}] JS error on {page.url}: {e}"))
            page.on("response", lambda r, lb=label: r.status >= 500 and problems.append(
                f"[{lb}] {r.status} from {r.url}"))
            page.goto(url + "/login")
            page.fill("input[autocomplete=username]", user)
            page.fill("input[autocomplete=current-password]", password)
            page.click("button[type=submit]")
            try:
                page.wait_for_url(re.compile(r".*/(change-password)?$"), timeout=10000)
            except Exception:
                sys.exit("Login failed — check the user name / password.")
            if "change-password" in page.url:
                sys.exit("This user must change their password first. Log in once in the browser.")

            targets = list(PAGES)
            for lst in DETAIL_LISTS:  # also open the first record of each list the user may see
                first_id = page.evaluate(
                    """async (p) => {
                        const r = await fetch('/api/v1' + p + '/?page_size=1', {headers:
                            {Authorization: 'Bearer ' + localStorage.getItem('arb_access')}});
                        if (!r.ok) return null;
                        const d = await r.json();
                        return d.results && d.results.length ? d.results[0].id : null;
                    }""",
                    lst,
                )
                if first_id:
                    targets.append(f"{lst}/{first_id}")

            for path in targets:
                page.goto(url + path)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(300)
                body = page.locator("body").inner_text()
                if ERROR_TEXT.search(body):
                    problems.append(f"[{label}] error screen on {path}")
                checked += 1
            page.context.close()
        browser.close()

    print(f"Checked {checked} page views as '{user}'.")
    if problems:
        print("PROBLEMS:")
        for p in dict.fromkeys(problems):
            print("  -", p)
        sys.exit(1)
    print("All good — no errors.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:5173")
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--headed", action="store_true", help="show the browser while testing")
    a = ap.parse_args()
    run(a.url.rstrip("/"), a.user, a.password, a.headed)
