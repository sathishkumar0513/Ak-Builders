# AK Builders — Database Schema & ER Diagram

PostgreSQL 16 · BigAutoField integer primary keys · all money `Decimal(12,2)` · quantities `Decimal(12,3)`.

> Open this file in **VS Code** (with the "Markdown Preview Mermaid Support" extension) or on **GitHub** to see the diagrams rendered.

## Conventions on every business table (`BaseModel`)

| Column | Purpose |
|---|---|
| `id` | BigAutoField primary key |
| `created_at`, `updated_at` | Timestamps (Asia/Kolkata) |
| `created_by`, `updated_by` | FK → User, filled automatically from the logged-in user |
| `is_deleted`, `deleted_at`, `deleted_by` | Soft delete — default manager hides deleted rows; `all_objects` shows everything |

Every create / update / soft-delete on a `BaseModel` table writes an **AuditLog** row with a field-level diff.

---

## 1. Masters, users and stock

```mermaid
erDiagram
    ROLE ||--o{ USER : "has"
    USER ||--o{ AUDIT_LOG : "performs"

    MATERIAL_CATEGORY ||--o{ MATERIAL : "groups"
    MATERIAL ||--o{ PRICE_HISTORY : "rate changes"
    MATERIAL ||--o{ STOCK_MOVEMENT : "stock ledger"
    PROJECT  |o--o{ STOCK_MOVEMENT : "site issues/returns"

    SUPPLIER ||--o{ PURCHASE : "supplies"
    PURCHASE ||--|{ PURCHASE_ITEM : "lines"
    MATERIAL ||--o{ PURCHASE_ITEM : "bought"
    SUPPLIER ||--o{ SUPPLIER_PAYMENT : "paid"
    PURCHASE |o--o{ SUPPLIER_PAYMENT : "against"

    ROLE {
           bigint id PK
           varchar code UK "SUPER_ADMIN|ADMIN|ACCOUNTANT|SITE_ENGINEER|SALES"
           varchar name
    }
    USER {
           bigint id PK
           varchar username UK
           varchar email UK
           varchar phone
           bigint role_id FK
           bool is_active
           timestamptz last_login
    }
    MATERIAL_CATEGORY {
           bigint id PK
           varchar name UK
    }
    MATERIAL {
           bigint id PK
           bigint category_id FK
           varchar name
           varchar brand
           varchar hsn_code
           varchar unit "bag|kg|ton|piece|sqft|load..."
           decimal purchase_price
           decimal selling_price
           decimal gst_rate
           decimal stock_quantity "CHECK >= 0"
           decimal reorder_level
    }
    PRICE_HISTORY {
           bigint id PK
           bigint material_id FK
           decimal old_selling_price
           decimal new_selling_price
           timestamptz changed_at
    }
    STOCK_MOVEMENT {
           bigint id PK
           bigint material_id FK
           varchar movement_type "PURCHASE_IN|SITE_ISSUE|SITE_RETURN|ADJUST..."
           decimal quantity
           decimal balance_after
           date date
           bigint project_id FK
           varchar reference_type
           bigint reference_id
    }
    SUPPLIER {
           bigint id PK
           varchar name
           varchar phone
           varchar gstin
           decimal opening_balance
    }
    PURCHASE {
           bigint id PK
           varchar po_number UK
           bigint supplier_id FK
           varchar supplier_invoice_number
           date purchase_date
           varchar status
           decimal grand_total
           decimal amount_paid
           decimal balance_due
    }
    PURCHASE_ITEM {
           bigint id PK
           bigint purchase_id FK
           bigint material_id FK
           decimal quantity
           decimal received_quantity "CHECK <= quantity"
           decimal rate
           decimal line_total
    }
    SUPPLIER_PAYMENT {
           bigint id PK
           varchar voucher_number UK
           bigint supplier_id FK
           bigint purchase_id FK
           decimal amount "CHECK > 0"
    }
    AUDIT_LOG {
           bigint id PK
           bigint user_id FK
           varchar action
           varchar model_name
           varchar object_id
           jsonb changes
           inet ip_address
           timestamptz timestamp
    }
```

## 2. Sales cycle: quotation → project → invoice → payment

```mermaid
erDiagram
    CUSTOMER ||--o{ QUOTATION : "receives"
    QUOTATION ||--|{ QUOTATION_ITEM : "lines"
    QUOTATION |o--o{ QUOTATION : "previous_revision"
    CUSTOMER ||--o{ PROJECT : "owns"
    QUOTATION |o--o{ PROJECT : "converted to"
    USER |o--o{ PROJECT : "assigned engineer"
    PROJECT ||--o{ PAYMENT_STAGE : "milestones 30/40/30"
    PROJECT ||--o{ PROJECT_MATERIAL_ISSUE : "material to site"
    PROJECT ||--o{ PROGRESS_NOTE : "daily notes"
    PROGRESS_NOTE ||--o{ PROGRESS_PHOTO : "photos"
    PROJECT |o--o{ EXPENSE : "labour, transport..."

    CUSTOMER ||--o{ INVOICE : "billed"
    PROJECT |o--o{ INVOICE : "billed for"
    PAYMENT_STAGE |o--o{ INVOICE : "stage bill"
    INVOICE ||--|{ INVOICE_ITEM : "lines"

    CUSTOMER ||--o{ ADVANCE_PAYMENT : "pays advance"
    ADVANCE_PAYMENT ||--o{ ADVANCE_ADJUSTMENT : "used on"
    INVOICE ||--o{ ADVANCE_ADJUSTMENT : "reduced by"
    ADVANCE_PAYMENT ||--o{ ADVANCE_REFUND : "refunded"

    CUSTOMER ||--o{ PAYMENT : "pays"
    INVOICE |o--o{ PAYMENT : "settles"
    PAYMENT_STAGE |o--o{ PAYMENT : "stage"
    CUSTOMER ||--o{ CUSTOMER_LEDGER_ENTRY : "account"

    CUSTOMER {
           bigint id PK
           varchar name
           varchar phone "indexed, 10-digit"
           varchar email
           varchar city
           varchar state_code "33 = Tamil Nadu"
           varchar gstin
           varchar customer_type "INDIVIDUAL|COMPANY"
    }
    QUOTATION {
           bigint id PK
           varchar number "UK with revision"
           smallint revision
           bool is_latest
           bigint customer_id FK
           date quotation_date
           date valid_until
           varchar status "DRAFT>SENT>APPROVED|REJECTED|EXPIRED>CONVERTED"
           bool is_interstate
           decimal taxable_amount
           decimal cgst_amount
           decimal sgst_amount
           decimal igst_amount
           decimal grand_total
    }
    QUOTATION_ITEM {
           bigint id PK
           bigint quotation_id FK
           varchar item_type "MATERIAL|SERVICE"
           bigint material_id FK
           varchar description
           decimal quantity
           decimal rate
           decimal discount_percent
           decimal gst_rate
           decimal line_total
    }
    PROJECT {
           bigint id PK
           varchar code UK
           bigint customer_id FK
           bigint quotation_id FK
           text site_address
           varchar status "PLANNED|IN_PROGRESS|ON_HOLD|COMPLETED"
           bigint assigned_engineer_id FK
           decimal contract_value
    }
    PAYMENT_STAGE {
           bigint id PK
           bigint project_id FK
           varchar name
           decimal percentage
           decimal amount
           date due_date
           decimal amount_received
    }
    PROJECT_MATERIAL_ISSUE {
           bigint id PK
           bigint project_id FK
           bigint material_id FK
           decimal quantity "CHECK > 0"
           decimal rate
           decimal amount
    }
    PROGRESS_NOTE {
           bigint id PK
           bigint project_id FK
           date date
           text note
    }
    PROGRESS_PHOTO {
           bigint id PK
           bigint note_id FK
           varchar image
    }
    INVOICE {
           bigint id PK
           varchar number UK "AK/2026-27/0001"
           bigint customer_id FK
           bigint project_id FK
           date invoice_date
           date due_date
           varchar status "UNPAID|PARTIAL|PAID|CANCELLED"
           decimal grand_total
           decimal advance_adjusted
           decimal amount_paid
           decimal balance_due "CHECK >= 0"
    }
    INVOICE_ITEM {
           bigint id PK
           bigint invoice_id FK
           varchar description
           decimal quantity
           decimal rate
           decimal line_total
    }
    ADVANCE_PAYMENT {
           bigint id PK
           varchar receipt_number UK
           bigint customer_id FK
           bigint project_id FK
           decimal amount "CHECK > 0"
           decimal adjusted_amount
           decimal refunded_amount "adjusted+refunded <= amount"
           varchar status
    }
    ADVANCE_ADJUSTMENT {
           bigint id PK
           bigint advance_id FK
           bigint invoice_id FK
           decimal amount
    }
    ADVANCE_REFUND {
           bigint id PK
           varchar refund_number UK
           bigint advance_id FK
           decimal amount
           varchar reason
    }
    PAYMENT {
           bigint id PK
           varchar receipt_number UK
           bigint customer_id FK
           bigint invoice_id FK
           bigint payment_stage_id FK
           date date
           decimal amount "CHECK > 0"
           varchar mode "CASH|UPI|BANK|CHEQUE|CARD"
           varchar reference_number
           varchar cheque_status
    }
    CUSTOMER_LEDGER_ENTRY {
           bigint id PK
           bigint customer_id FK
           date date
           varchar entry_type
           decimal debit
           decimal credit
           varchar reference_number
    }
    EXPENSE {
           bigint id PK
           varchar voucher_number UK
           bigint project_id FK
           varchar category "LABOUR|TRANSPORT|SITE|MISC..."
           date date
           decimal amount "CHECK > 0"
    }
```

## 3. Settings tables

| Table | Notes |
|---|---|
| `core_companysettings` | Single row (id = 1): name, logo, address, GSTIN, state code **33 (Tamil Nadu)**, bank + UPI details, default GST %, quotation validity, invoice due days, notification switches |
| `core_documentsequence` | One row per document type per financial year. Unique `(doc_type, financial_year)`. Locked with `SELECT … FOR UPDATE` when issuing numbers |
| `core_termstemplate` | Reusable terms & conditions for quotations / invoices / receipts |
| `payments_paymentreminder` | Scheduled reminders (email / SMS / WhatsApp) for overdue invoices and stages |

## 4. Document number series

| Document | Format | Example |
|---|---|---|
| Invoice | `AK/{FY}/{0000}` | AK/2026-27/0001 |
| Quotation | `AK/QT/{FY}/{0000}` + revision | AK/QT/2026-27/0007 Rev 2 |
| Advance receipt | `AK/ADV/{FY}/{0000}` | AK/ADV/2026-27/0003 |
| Payment receipt | `AK/RCP/{FY}/{0000}` | AK/RCP/2026-27/0012 |
| Purchase order | `AK/PO/{FY}/{0000}` | AK/PO/2026-27/0004 |
| Project | `AK/PRJ/{FY}/{0000}` | AK/PRJ/2026-27/0002 |
| Expense voucher | `AK/EXP/{FY}/{0000}` | AK/EXP/2026-27/0040 |

Financial year runs April → March and numbering restarts at 0001 each April. Prefixes can be edited in Django admin → Document sequences.

## 5. Money rules built into the schema

| Rule | Where it is enforced |
|---|---|
| No float money | Every amount is `MoneyField` = `Decimal(12,2)` with a `>= 0` validator |
| Stock never below zero | DB `CHECK (stock_quantity >= 0)` + service validation (Phase 3) |
| Payment / advance / expense amount > 0 | DB `CHECK` constraints |
| Advance not over-used | DB `CHECK (amount >= adjusted_amount + refunded_amount)` |
| Invoice balance never negative (no over-payment) | DB `CHECK (balance_due >= 0)` + service check |
| Received qty ≤ ordered qty | DB `CHECK` on `PurchaseItem` |
| Unique document numbers | `UNIQUE` on every number column; quotation unique on `(number, revision)` |
| GST split | Same state as company (33) → CGST + SGST; other state → IGST (`apps/core/utils.py`) |
| Atomic financial operations | All posting services use `transaction.atomic()` (Phases 3–5) |

## 6. Customer ledger posting (Phase 5)

| Event | Debit | Credit |
|---|---|---|
| Invoice issued | grand total | |
| Advance received | | amount |
| Payment received | | amount |
| Advance adjusted on invoice | — | — (already credited when received) |
| Advance refunded | amount | |
| Invoice cancelled | | grand total |
| Cheque bounced | amount | |

**Outstanding = Σ debit − Σ credit.** A negative result means the customer has unused advance with us.
