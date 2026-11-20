# AK Builders Management System

Web application for **AK Builders** (renovation & construction, Tamil Nadu) covering customers, building materials and stock, suppliers and purchases, GST quotations, projects and sites, advance payments, stage payments, GST invoices, expenses and reports.

| Layer | Technology |
|---|---|
| Frontend | React 18 (Vite), React Router, TanStack Query, Axios, Tailwind CSS, React Hook Form + Zod |
| Backend | Django 5.2 LTS + Django REST Framework, SimpleJWT, django-filter, drf-spectacular |
| Database | PostgreSQL 16 |
| PDF | ReportLab (works on Windows without GTK — chosen over WeasyPrint for that reason) |
| Jobs | Celery + Redis (optional, for payment reminders) |
| Deploy | Docker Compose, Gunicorn, Nginx |

Locale: currency ₹ INR with lakh/crore grouping, dates shown as **DD/MM/YYYY**, time zone Asia/Kolkata, GST home state **Tamil Nadu (33)**. A customer in state 33 is billed CGST + SGST; a customer in any other state is billed IGST.

---

## Project structure

```
AK Builder/
├── backend/                     Django project
│   ├── config/                  settings (base / dev / test / prod), urls, wsgi, celery
│   ├── apps/
│   │   ├── core/                base models, soft delete, audit log, company settings,
│   │   │                        number series, INR/GST helpers, seed_data command
│   │   ├── accounts/            User (custom) + Role
│   │   ├── customers/           Customer
│   │   ├── materials/           Category, Material, PriceHistory, StockMovement
│   │   ├── suppliers/           Supplier, Purchase, PurchaseItem, SupplierPayment
│   │   ├── quotations/          Quotation (versioned), QuotationItem
│   │   ├── projects/            Project, PaymentStage, MaterialIssue, ProgressNote/Photo
│   │   ├── invoices/            Invoice, InvoiceItem
│   │   ├── payments/            Advance, AdvanceAdjustment, AdvanceRefund, Payment,
│   │   │                        CustomerLedgerEntry, PaymentReminder
│   │   ├── expenses/            Expense
│   │   └── reports/             (computed reports — Phase 6)
│   ├── requirements.txt / requirements-dev.txt
│   ├── Dockerfile, entrypoint.sh
│   └── .env                     local secrets (not committed)
├── frontend/                    React app
│   ├── src/
│   │   ├── api/                 axios client, react-query client
│   │   ├── components/          layout (Sidebar, Topbar, Breadcrumbs), ui
│   │   ├── config/navigation.js role-based menu
│   │   ├── layouts/ pages/ routes/ hooks/ utils/
│   ├── nginx/default.conf       production Nginx (serves React + proxies /api)
│   └── Dockerfile
├── docs/ER_DIAGRAM.md           schema, ER diagrams, money rules, number series
├── docs/er-*.png                ER diagrams as images
├── scripts/                     Windows setup/run, backup/restore (PowerShell), Docker backup
├── docker-compose.yml
└── .env.docker.example
```

**Each app follows the same layout from Phase 2 onwards:** `models.py` → `serializers.py` → `services.py` (all business logic and `transaction.atomic()`) → `views.py` (thin ViewSets) → `permissions.py` → `urls.py` → `tests/`.

---

## Option A — run locally on Windows (development)

### Prerequisites
- **Python 3.11 or 3.12** — tick "Add python.exe to PATH" in the installer
- **Node.js 20 LTS or 22 LTS**
- **PostgreSQL 16** (running on `localhost:5432`, user `postgres`) — add `C:\Program Files\PostgreSQL\16\bin` to PATH so `psql` and `pg_dump` work

### Quick setup (one command)
Open **Command Prompt** in `D:\new project\AK Builder` and run:
```bat
scripts\setup_windows.bat
scripts\run_dev.bat
```
The setup script creates the `arbuilders` database, a Python virtualenv, installs packages, runs migrations, loads seed data and installs the npm packages. `run_dev.bat` opens the backend and frontend in two windows and opens the browser.

### Manual setup (same steps, one by one)
```bat
:: 1. Database
psql -U postgres -h localhost -c "CREATE DATABASE arbuilders"

:: 2. Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver

:: 3. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

`backend\.env` already holds your local PostgreSQL password. Copy `backend\.env.example` when setting up another machine.

### Open
| URL | What |
|---|---|
| http://localhost:5173 | React app |
| http://localhost:8000/api/docs/ | Swagger API docs |
| http://localhost:8000/admin/ | Django admin (log in with the demo admin) |
| http://localhost:8000/api/v1/health/ | Health check |

**Demo admin:** `admin` / `Admin@12345` (set in `backend\.env`, flagged "must change password").

**Test on a phone:** connect the phone to the same Wi-Fi and open `http://<your-PC-IP>:5173` (Vite listens on all interfaces). Find the IP with `ipconfig`.

---

## Option B — run with Docker

```bash
copy .env.docker.example .env        # Windows   (Linux: cp .env.docker.example .env)
# edit .env → set DB_PASSWORD, SECRET_KEY, ALLOWED_HOSTS
docker compose up -d --build
docker compose --profile worker up -d   # optional: Redis + Celery for reminders
```
App: http://localhost · API docs: http://localhost/api/docs/

On the first start, `SEED_ON_START=True` loads the seed data. Set it to `False` after that.

Useful commands:
```bash
docker compose logs -f backend
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py migrate
docker compose down            # stop (data is kept in the pgdata volume)
```

---

## Migrations

Initial migrations for every app are already included. After changing any `models.py`:
```bat
python manage.py makemigrations
python manage.py migrate
python manage.py makemigrations --check --dry-run   :: confirms nothing is pending
```

## Tests and code style
```bat
cd backend
pytest                     :: unit tests (money, GST split, amount in words, number series, soft delete, seed)
flake8 && black --check . && isort --check .

cd frontend
npm run lint
npm run format
```

---

## Backups (PostgreSQL)

| Setup | Command | Schedule |
|---|---|---|
| Windows local | `powershell -ExecutionPolicy Bypass -File scripts\backup_db.ps1` | Task Scheduler, daily |
| Docker server | `./scripts/backup_docker.sh` | cron `0 22 * * *` |
| Restore (Windows) | `scripts\restore_db.ps1 -File backups\arbuilders_YYYY-MM-DD_HHMM.dump` | — |

Backups use `pg_dump -F c` (compressed, restorable with `pg_restore`), are kept for 30 days in `backups/`, and the Docker script copies them off-site with `rclone` when it is configured. **Keep at least one copy off this PC** (Google Drive, external disk).

---

## Seed data
`python manage.py seed_data` (safe to run again) creates:
- 5 roles: Super Admin, Admin, Accountant, Site Engineer, Sales/Staff
- the demo Super Admin user
- company settings (AK Builders, Tamil Nadu 33)
- 10 categories and 22 materials with opening stock: Cement (UltraTech, Ramco, Dalmia), **TMT Rod 8/10/12/16 mm**, binding wire, **Jalli** (weld mesh, chicken mesh), **Bricks** (red, fly-ash, blocks), **Sand** (M-sand, P-sand), blue metal, paint, putty, tiles, PVC pipe, copper wire
- default quotation and invoice terms & conditions

⚠️ Prices and GST rates in the seed are **sample values**. Confirm the current HSN rates with your accountant before billing.

---

## Delivery phases

| Phase | Scope | Status |
|---|---|---|
| 1 | Project setup, folder structure, DB schema + ER diagram, Docker | ✅ Done |
| 2 | Auth (JWT login/refresh/logout, forgot/reset/change password), RBAC, user CRUD, audit log, company settings, protected React routes | ✅ Done |
| 3 | Customer, Material (price history, low stock), Supplier & Purchase (auto stock increase) | ✅ Done |
| 4 | Quotation (line items, GST, revisions, PDF, WhatsApp/email share, convert to project) | ✅ Done |
| 5 | Project, Advance, Payment, Invoice (auto-adjust, ledger, receipts) | ✅ Done |
| 6 | Expenses, Dashboard, Reports, Excel/PDF export | ✅ Done |
| 7 | Testing & security hardening ✅ · Deployment (server, HTTPS, backups) — on hold | 🟡 Part done |

---

## Phase 2 — Authentication & roles

### Who can do what

| Area | Super Admin | Admin | Accountant | Site Engineer | Sales / Staff |
|---|:-:|:-:|:-:|:-:|:-:|
| Dashboard, Materials (view), Projects | ✅ | ✅ | ✅ | ✅ | ✅ |
| Customers, Quotations | ✅ | ✅ | ✅ | — | ✅ |
| Suppliers, Advances, Payments, Invoices, Reports | ✅ | ✅ | ✅ | — | — |
| Expenses | ✅ | ✅ | ✅ | ✅ | — |
| Users, Audit log, Company settings | ✅ | ✅ | — | — | — |
| Edit document number series | ✅ | — | — | — | — |
| Create / change a Super Admin | ✅ | — | — | — | — |

The same rules are enforced twice: the React menu and routes hide what a role can't use, and every API checks the role again (`apps/accounts/permissions.py → RoleBasedPermission`). Fine-grained per-module rules (for example, a site engineer seeing only assigned projects) are added with each module.

### Security behaviour
- **Login** with username *or* email. 5 attempts per minute per IP (`LOGIN_THROTTLE_RATE`), then HTTP 429. Every success and failure is in the audit log.
- **Tokens:** access token 30 min, refresh token 7 days, rotated on every refresh. The old refresh token is blacklisted. The React app refreshes silently, and parallel requests wait for one refresh.
- **Temporary passwords:** users created by an Admin, or reset by an Admin, must change their password at the next login (the app forces the Change Password screen).
- **Change password / reset / deactivate** → all other sessions of that user are logged out immediately.
- **Forgot password** emails a link valid for 2 hours. It always shows the same message, so it doesn't reveal which emails exist. In development the email is printed in the **backend terminal window**. Set `EMAIL_*` in `.env` to send real email (Gmail: use an App Password).
- Protections: you can't deactivate or delete yourself or change your own role, an Admin can't touch a Super Admin, and the last active Super Admin can't be removed.

### API endpoints (all under `/api/v1/`, full docs at `/api/docs/`)

| Method | URL | Who |
|---|---|---|
| POST | `auth/login/` `{username, password}` → `{access, refresh, user}` | anyone |
| POST | `auth/refresh/` `{refresh}` | anyone with a valid refresh token |
| POST | `auth/logout/` `{refresh}` | logged in |
| GET / PATCH | `auth/me/` | logged in |
| POST | `auth/change-password/` | logged in |
| POST | `auth/forgot-password/` · `auth/reset-password/` | anyone (rate-limited) |
| GET POST / GET PATCH DELETE | `users/` · `users/{id}/` | Super Admin, Admin |
| POST | `users/{id}/activate/` · `deactivate/` · `reset-password/` | Super Admin, Admin |
| GET | `roles/` | Super Admin, Admin |
| GET | `audit-logs/?action=&model_name=&user=&date_from=&date_to=&search=` | Super Admin, Admin |
| GET / PATCH | `settings/company/` (multipart for logo) | GET everyone · PATCH Super Admin, Admin |
| GET / PATCH | `settings/sequences/` | GET Super Admin, Admin · PATCH Super Admin |
| GET | `lookups/` (states, payment modes, units) | logged in |

In Swagger, click **Authorize** and paste the `access` token from the login response.

### Reusable frontend building blocks (used by every later module)
`DataTable` (sorting, pagination, skeletons, card layout on phones) · `Modal` (bottom sheet on phones) · `useConfirm()` dialog · `Field / Input / Select` (React Hook Form) · `SearchInput` (debounced) · `useListParams` (filters kept in the URL) · `exportCsv` · `applyFieldErrors` (shows server validation under the right field).

### Try it
1. Log in as `admin` / `Admin@12345`. You'll be asked to set a new password.
2. **Users → Add user**: create a Sales user with a temporary password.
3. Open a private window (or your phone), log in as that user, set a password, and check that Users / Settings are hidden and `/users` shows "Access denied".
4. **Audit log**: see the logins, user creation and password changes.
5. **Settings**: fill in GSTIN, bank and UPI details and upload the logo (used on PDFs from Phase 4).

---

## Phase 3 — Customers, Materials & stock, Suppliers & Purchases

### How stock works
Stock is **never typed in directly**. Every change goes through one service (`apps/materials/services.py → record_movement`), which locks the material row, refuses to go below zero and writes a `StockMovement` row with the running balance. That gives a complete stock history per material:

| Event | Movement | Who |
|---|---|---|
| New material with opening stock | `OPENING` + | Accountant, Admin |
| Purchase goods received (full or part) | `PURCHASE_IN` + | Accountant, Admin |
| Manual correction (damage, count mismatch) — reason required | `ADJUST_IN` / `ADJUST_OUT` | Admin |
| Material issued to / returned from a site | `SITE_ISSUE` − / `SITE_RETURN` + | Phase 5 |

**Low stock** = stock ≤ reorder level. Shown as a red banner on Materials, a filter, a warning on the material page, and `GET /api/v1/materials/low-stock/` (used by the dashboard in Phase 6).

**Price history:** every change to purchase or selling price is recorded with old → new values, the reason and who changed it. Receiving a purchase updates the purchase price to that bill's **net unit cost** (rate after discount, excluding GST, since GST is input credit). You can switch this off per receipt.

**Who sees cost:** Sales and Site Engineers never receive `purchase_price` or stock value from the API. It's removed on the server, not just hidden in the browser.

### GST calculation (shared by purchases now, quotations and invoices next)
`apps/core/calculations.py` (server) and `src/utils/gst.js` (live preview) use identical rules, so the preview always matches the saved total to the paisa:
- line: qty × rate − discount % = taxable → GST at the line's rate
- **same state as the company (33 Tamil Nadu) → CGST + SGST** (odd paise go to CGST); **other state → IGST**
- a header discount is spread over lines *before* tax, transport/other charges are added after tax, and the grand total is rounded to the nearest rupee, with the amount in words in Indian format.

### Purchase flow
1. **New purchase**: pick the supplier (state decides IGST), add material lines (rate, unit, HSN and GST auto-fill from the material master) and service lines (unloading, transport…). Totals update live.
2. Tick **Goods received now** for a normal bill, or leave it unticked for a purchase order and **Receive goods** later (part deliveries allowed, and you can never receive more than ordered).
3. **Record payment** against the bill, or **Pay supplier** on account from the supplier page. You can't pay more than is due. An Admin can cancel a wrong payment, which restores the balance.
4. A purchase can be edited until goods are received, and cancelled (Admin) only if nothing has been received or paid. Duplicate supplier bill numbers are blocked.

**Supplier payable** = opening balance + purchases (not cancelled) − payments.

### Customers
Mobile numbers are normalised (`+91 98765-43210` → `9876543210`) and must be unique, and the error names the existing customer. GSTIN is uppercased and must match the state. Company customers need a contact person. The detail page has Call / WhatsApp / Email buttons, outstanding, advance balance, and tabs for quotations, projects and payments (filled from Phase 4–5). Delete is soft (Admin), and `POST /customers/{id}/restore/` brings a record back.

### New API endpoints
`customers/` (+ `{id}/summary/`, `cities/`, `{id}/restore/`) · `materials/` (+ `{id}/adjust-stock/`, `{id}/movements/`, `{id}/price-history/`, `low-stock/`) · `material-categories/` · `stock-movements/` · `suppliers/` · `purchases/` (+ `{id}/receive/`, `{id}/cancel/`) · `supplier-payments/`. All with search, filters, ordering and pagination. See `/api/docs/`.

---

## Phase 4 — Quotations

### Status flow
```
DRAFT ──Mark as sent──▶ SENT ──Customer approved──▶ APPROVED ──Convert to project──▶ CONVERTED
  │                      │  └──Customer rejected──▶ REJECTED
  │                      └──(valid-until date passes)──▶ EXPIRED   (automatic, daily)
  └── approve / reject directly if the customer replied before you marked it sent
```
- **Only drafts are edited.** To change a sent, approved, rejected or expired quotation, use **Revise**. That creates **Rev 2, 3…** with the same number as a new draft. Older revisions stay read-only in the history panel, and lists show only the latest revision (`?all_revisions=true` in the API shows all).
- Expiry runs daily through Celery beat (`expire-quotations-daily`), and also every time the quotation list is opened, so it works without Celery. Manual run: `python manage.py expire_quotations`.
- **Convert to project** (Admin / Super Admin, approved quotations only) creates a project with the contract value = grand total, the customer, the site address, an optional site engineer and dates, plus **payment stages** (default 30 / 40 / 30, editable, must total 100%, and the last stage absorbs rounding so the stages add up exactly). The quotation becomes *Converted* and is locked.
- **Duplicate** copies a quotation as a new number (useful for similar jobs).

### GST on quotations
Place of supply = the customer's state. Tamil Nadu (33) → CGST + SGST, any other state → IGST. The overall discount is applied **before** GST and spread across lines in proportion to their value. Tax is rounded per line, and the odd paisa goes to CGST, so CGST and SGST can differ by ₹0.01 while total tax stays exact.

### PDF, print and sharing
- `GET /api/v1/quotations/{id}/pdf/` gives an A4 PDF with logo, GSTIN, customer and site boxes, an HSN-wise item table, a GST summary by rate, totals, amount in words (Indian format), notes, terms, bank/UPI details and a signature block. `?download=1` forces a download.
- Generated with **ReportLab** and the bundled **DejaVu Sans** font (`backend/assets/fonts`, free licence included) so **₹ prints correctly on Windows, Linux and Docker** without installing anything.
- **WhatsApp**: on a phone the share sheet opens with the **PDF attached**; pick WhatsApp and the customer. On a desktop the PDF downloads and WhatsApp Web opens the customer's chat with a ready message, so you just attach the file. You're then asked whether to mark the quotation as sent.
- **Email**: sends the PDF as an attachment to the customer (plus CC) and marks a draft as sent. In development the email appears in the backend window. Set `EMAIL_*` in `.env` for real sending.

### Terms & conditions templates
**Settings → Terms & conditions** holds several templates per document type (quotation / invoice / receipt). The default one fills new quotations automatically, and any template can be applied from the quotation form.

### New API endpoints
`quotations/` (+ `{id}/send/`, `approve/`, `reject/`, `revise/`, `duplicate/`, `convert/`, `pdf/`, `share-text/`, `email/`) · `settings/terms/` · `users/lookup/?role=SITE_ENGINEER`.

---

## Phase 5 — Projects, Advances, Payments & Invoices

### Money flow in one picture
```
Advance (AK/ADV) ──auto-adjust──▶ Invoice (AK/2026-27/0001) ◀── Payment (AK/RCP)
      │                                   │                         │
      └── Refund (AK/REF)                 └── Customer ledger ◀─────┘
```
- **Invoice** = from a project stage (one click), from an approved quotation (prefilled), or blank. Numbering restarts every financial year: `AK/2026-27/0001`.
- **Auto-adjust advances**: when an invoice is saved, unused advances are applied automatically: **advances for the same project first, then general (no-project) advances**, oldest first. You can untick this, adjust manually from the advance page, or remove an adjustment (Accountant / Admin).
- **Invoice balance** = grand total − (payments not bounced + advance adjustments). Status moves UNPAID → PARTIAL → PAID automatically, and the PDF shows *Advance adjusted / Received / Balance due* and a **PAID** or **CANCELLED** watermark.
- **Payments** must point to an invoice or a project stage, can't exceed what's due, and can't be dated before the invoice. A **cheque** can be marked cleared or **bounced**. A bounce reopens the balance and posts a debit on the ledger.
- **Cancel rules**: an invoice can only be edited while unpaid, and can only be cancelled when it has no payments (its advance adjustments are released). Payments, advances and refunds are cancelled with a reason, never deleted.

### Customer ledger (Customer → Ledger tab, Accountant / Admin)
| Event | Entry |
|---|---|
| Invoice | Debit |
| Advance received, payment received | Credit |
| Refund, cheque bounce | Debit |
| Any cancellation | Reversal entry (the original stays visible) |
| Advance adjusted against an invoice | No entry (the money was already credited) |

Balance shows **Dr** (customer owes) or **Cr** (customer has credit). Filter by dates and export to CSV.

### Projects & sites
- **Payment stages** must total 100%. Paid or invoiced stages are locked; the rest are rescaled when the contract value changes. Each stage has **Invoice** and **Payment** buttons. A stage invoice treats the amount as GST-inclusive at 18% (SAC 995411).
- **Site material**: issuing material reduces store stock (`SITE_ISSUE`) and adds to project cost; **Return to store** reverses it. A project's invoice never deducts stock again.
- **Progress** updates with % complete, notes and up to 10 photos (images only, ≤ 8 MB each).
- **Summary** (Accountant / Admin): contract value, billed, received, outstanding, cost so far (material now, expenses in Phase 6) and expected profit.
- **Site engineers** see only projects assigned to them, only the *Site material* and *Progress* tabs, and no money figures. They can't open invoices, payments or advances.

### Receipts & sharing
Receipt PDFs for payments, advances and refunds (with the invoice balance after the payment), plus WhatsApp share text and **payment reminders** for overdue invoices (`invoices/overdue/`, the reminder is logged).

### New API endpoints
`projects/` (+ `{id}/summary/`, `stages/`, `status/`, `materials/`, `issue-material/`, `materials/{issue_id}/` DELETE, `progress/`, `add-progress/`) · `invoices/` (+ `from-stage/`, `prefill/?quotation=`, `overdue/`, `{id}/cancel/`, `pdf/`, `share-text/?reminder=1`, `log-reminder/`, `email/`) · `advances/` (+ `{id}/adjust/`, `refund/`, `cancel/`, `pdf/`, `refunds/{rid}/pdf/`) · `advance-adjustments/{id}/` DELETE · `payments/` (+ `{id}/cancel/`, `cheque/`, `pdf/`, `share-text/`) · `customers/{id}/ledger/`, `customers/{id}/open-items/`.

### After updating
Three new migrations (projects 0002, payments 0002, invoices 0003). **Close and re-run `scripts\run_dev.bat`**, which runs `migrate` on start (from Phase 6 onwards). With Docker: `docker compose exec backend python manage.py migrate`.

---

## Phase 6 — Expenses, Dashboard & Reports

### Expenses
- Categories: labour wages, transport, site expense, local material, equipment hire, fuel, office / rent, miscellaneous. Voucher numbers `AK/EXP/2026-27/0001`.
- **Labour:** enter workers × days × wage per day and the amount fills itself.
- **Project or office:** an expense linked to a project goes into that project's cost and profit; one without a project is office overhead.
- **Approval:** expenses entered by a **Site Engineer** wait for approval by an Accountant or Admin. Until then the engineer can still edit them; after approval they're locked. Expenses entered by the office are approved immediately.
- Site engineers can only add expenses to **their own projects** and only see those expenses. Sales staff don't see expenses.
- Attach a bill photo or PDF (≤ 8 MB). Dates can't be in the future. Delete is Admin-only and soft (kept in the audit log).
- Every project now has an **Expenses** tab, and the list page shows totals per category (click one to filter).

### Dashboard (changes by role)
| Shown to | What |
|---|---|
| Everyone | Active projects (engineers: theirs), low-stock items, projects by status |
| Sales and above | Total customers, pending quotations, quotations expiring this week |
| Accountant / Admin | Received this year and month, total outstanding and overdue, billed this year, expenses this month and pending approvals; **monthly revenue chart** (billed / received / expenses, 12 months), **payment-mode split**, top customers, overdue invoices, recent receipts |
| Site engineer | My active sites with progress, my expenses awaiting approval |

Cards are clickable and open the matching list or report. Charts are plain SVG (no extra package) and work offline and in dark mode.

### Reports (Accountant / Admin)
| Report | What it answers |
|---|---|
| Payments received | Payments + advances − refunds by date, customer and mode (bounced cheques excluded) |
| Outstanding & ageing | Every unpaid invoice: days overdue, bucket (not due, 1–30, 31–60, 61–90, 90+) |
| Customer-wise outstanding | Billed, received, unused advance, dues and overdue per customer |
| Customer ledger | Debit / credit statement with running balance for one customer |
| Sales register (GST) | Invoice-wise taxable value, CGST, SGST, IGST: use for GSTR-1 |
| Quotation conversion | Quotations created / won / rejected / expired per month and the conversion rate |
| Project profit / loss | Contract, billed, received, material + expenses, cash profit, expected margin |
| Expenses | By category, by project or entry by entry |
| Stock summary | Opening, in, out, closing quantity and value per material for any period |
| Material purchases | By material (with average rate), by supplier, or bill line by line |

- Date range defaults to the **current financial year** (April → today), with quick buttons: This month, Last month, This FY, Last FY. Filters stay in the URL, so a report link can be bookmarked or shared.
- **Excel** (real numbers and dates, frozen header, filters, totals row) and **PDF** (company header, KPI strip, landscape for wide reports, page numbers) use exactly the same filters as the screen. Every export is written to the audit log.
- API: `GET /api/v1/reports/` (list) · `GET /api/v1/reports/{key}/?date_from=&date_to=&customer=&…` · add `&export=xlsx` or `&export=pdf` to download.

### New API endpoints
`expenses/` (+ `{id}/approve/`, `{id}/remove-bill/`, `summary/`) · `dashboard/` · `reports/` · `reports/{key}/`.

### After updating
One new migration (expenses 0003). `scripts\run_dev.bat` now runs `migrate` automatically every time it starts.

---

## Phase 7 — Testing & security (deployment comes later)

### Running the tests
| What | Command | Notes |
|---|---|---|
| Backend: 145 tests, 95 % code coverage | `cd backend` → `venv\Scripts\activate` → `pip install -r requirements-dev.txt` (once) → `pytest --cov=apps` | uses a separate throw-away test database |
| Frontend: 308 tests | `cd frontend` → `npm test` | GST preview, Indian formatting, CSV safety |
| Browser smoke test | `pip install playwright` and `python -m playwright install chromium` (once), then `python e2e/smoke_test.py --user admin --password "…"` | **read-only**: opens every page for that role on desktop and phone sizes; safe on real data |
| Security audit of packages | `pip-audit -r backend/requirements.txt` · `cd frontend && npm audit` | |
| Everything automatically | `.github/workflows/ci.yml` | runs on every push if the code is kept on GitHub |

**What the tests cover beyond the per-module tests:**
- **Permission sweep:** every API list endpoint is called as all 5 roles plus a logged-out user. Each answer must match the access table (Phase 2), and no combination may produce a server error.
- **GST parity:** the same 300 generated invoices (mixed rates, line and header discounts, transport, IGST) are calculated by the server (Python) and by the live preview (JavaScript), and must match to the paisa.
- **Security regression tests** for each item below.

### Security measures
| Risk | Protection |
|---|---|
| Password guessing | 5 wrong logins per minute per IP (throttle) **and** per account: 5 wrong passwords lock that account for 15 minutes, even from different IPs. Lockouts are written to the audit log. |
| Weak passwords | Minimum 8 characters, not common, not all numbers, not similar to the user name. |
| Stolen / old tokens | 30-minute access tokens, 7-day refresh tokens rotated and blacklisted on use; logout, password change, reset and deactivation end all sessions. Forged or `alg:none` tokens are rejected (tested). |
| Raising your own access | Role comes from the database, never from the token or the request; users can't change their own role (tested). |
| Seeing other people's data | Site engineers only reach their own projects and expenses (404 otherwise); cost prices are removed on the server for Sales and Site Engineers (tested). |
| Malicious uploads | Files are checked by **content**, not name or browser type: photos must open as real JPG/PNG/WebP/GIF images, bills must be a photo or a real PDF. SVG/HTML are refused, oversized "decompression bomb" images are refused, size limits apply (logo 2 MB, others 8 MB, max 12 files per request). Stored under **random names**, so links can't be guessed and uploads can't overwrite each other. |
| Spreadsheet formula injection | Text starting with `=`, `+`, `-`, `@` (e.g. a customer named `=HYPERLINK(...)`) is neutralised in Excel and CSV exports. |
| Overload / scraping | 60 requests/min for anonymous users, 600/min per logged-in user, 30 Excel/PDF exports per minute per user. |
| Bad input | Every list ignores unknown ordering fields; dates, IDs and report filters are validated (no server errors on odd input; tested). |
| Browser attacks | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`, `Cross-Origin-Opener-Policy`; no `dangerouslySetInnerHTML` anywhere in the React code. |
| Misconfigured production | `prod.py` refuses to start with the sample `SECRET_KEY` or empty `ALLOWED_HOSTS`; `DEBUG` is always off; HTTPS, HSTS and secure cookies switch on with `USE_HTTPS=True`; the Django admin path can be moved (`ADMIN_URL`). `python manage.py check --deploy` is clean. |
| Known library bugs | Upgraded **Pillow 11 → 13** and **Django REST Framework 3.16 → 3.18** (published security fixes). `pip-audit`: no known issues. |

**Open npm advisories (reviewed, not exploitable here):** `react-router` (an open redirect through user-supplied link targets, and server-side rendering, neither of which this app uses) and `zod` (memory use on huge arrays; zod only checks form input typed by the logged-in user). The fixes need major-version rewrites (React Router 7, Zod 4); planned for the deployment step.

### Left for deployment (on hold until you ask)
Server setup with Docker + Gunicorn + Nginx, HTTPS certificate, a strong `SECRET_KEY` / `ADMIN_URL` / `ALLOWED_HOSTS`, `CACHE_URL` (Redis) so lockouts work across workers, a Content-Security-Policy header in Nginx, scheduled backups with an off-site copy and a restore test, and the go-live checklist.

### After updating
`scripts\run_dev.bat` now also installs new packages before starting (needed this time: Pillow and Django REST Framework were upgraded). Just close both windows and run it again. Three small migrations change how uploaded files are named; existing files keep working.
