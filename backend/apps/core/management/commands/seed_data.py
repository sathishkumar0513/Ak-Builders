"""
python manage.py seed_data

Creates (safe to run many times — it never duplicates):
- the 5 roles
- a demo Super Admin user (credentials from .env: DEMO_ADMIN_USERNAME / DEMO_ADMIN_PASSWORD)
- company settings for AK Builders (Tamil Nadu, state code 33)
- material categories and sample materials with opening stock
- default terms & conditions templates

NOTE: prices and GST rates below are SAMPLE values. Confirm current rates with your accountant.
"""

from datetime import date
from decimal import Decimal as D

from decouple import config
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, User
from apps.core.models import CompanySettings, DocumentSequence, TermsTemplate
from apps.core.numbering import DEFAULT_PREFIXES
from apps.core.utils import financial_year
from apps.materials.models import Material, MaterialCategory, StockMovement

ROLES = [
    (Role.SUPER_ADMIN, "Super Admin", "Full access including settings and user management"),
    (Role.ADMIN, "Admin", "Manages users, masters, quotations, projects and billing"),
    (Role.ACCOUNTANT, "Accountant", "Invoices, payments, advances, expenses, reports"),
    (Role.SITE_ENGINEER, "Site Engineer", "Assigned projects, material issue, progress notes and photos"),
    (Role.SALES, "Sales / Staff", "Customers and quotations"),
]

CATEGORIES = [
    ("Cement", "OPC / PPC cement bags"),
    ("Steel", "TMT bars and binding wire"),
    ("Jalli", "Weld mesh, chicken mesh, grills"),
    ("Bricks", "Red bricks, fly-ash bricks, blocks"),
    ("Sand", "River sand, M-sand, P-sand"),
    ("Aggregate", "Blue metal / jalli stones"),
    ("Paint", "Interior, exterior, primer, putty"),
    ("Tiles", "Floor and wall tiles"),
    ("Plumbing", "Pipes, fittings, sanitary"),
    ("Electrical", "Wires, switches, conduits"),
]

# (category, name, brand, hsn, unit, purchase, selling, gst, opening_stock, reorder)
MATERIALS = [
    ("Cement", "OPC 53 Grade Cement", "UltraTech", "2523", "bag", "370", "410", "18", "200", "50"),
    ("Cement", "PPC Cement", "Ramco", "2523", "bag", "355", "395", "18", "150", "50"),
    ("Cement", "PPC Cement", "Dalmia", "2523", "bag", "350", "390", "18", "100", "40"),
    ("Steel", "TMT Rod 8 mm", "JSW Neosteel", "7214", "kg", "62", "70", "18", "1000", "200"),
    ("Steel", "TMT Rod 10 mm", "JSW Neosteel", "7214", "kg", "61", "69", "18", "1500", "300"),
    ("Steel", "TMT Rod 12 mm", "JSW Neosteel", "7214", "kg", "60", "68", "18", "2000", "400"),
    ("Steel", "TMT Rod 16 mm", "JSW Neosteel", "7214", "kg", "60", "68", "18", "1500", "300"),
    ("Steel", "Binding Wire", "Local", "7217", "kg", "75", "90", "18", "100", "25"),
    ("Jalli", "Weld Mesh Jalli 2x2 inch", "Local", "7314", "sqft", "28", "36", "18", "500", "100"),
    ("Jalli", "Chicken Mesh Jalli", "Local", "7314", "sqft", "12", "16", "18", "400", "100"),
    ("Bricks", "Red Clay Bricks (chamber)", "Local kiln", "6901", "nos", "8.50", "10", "5", "10000", "2000"),
    ("Bricks", "Fly Ash Bricks", "Local", "6810", "nos", "6.50", "8", "5", "8000", "2000"),
    ("Bricks", "Solid Concrete Block 6 inch", "Local", "6810", "nos", "38", "45", "5", "1000", "200"),
    ("Sand", "M-Sand", "Local quarry", "2505", "load", "4500", "5200", "5", "5", "2"),
    ("Sand", "P-Sand (plastering)", "Local quarry", "2505", "load", "5200", "6000", "5", "4", "2"),
    ("Aggregate", "Blue Metal 20 mm", "Local quarry", "2517", "load", "4200", "4900", "5", "4", "2"),
    ("Aggregate", "Blue Metal 40 mm", "Local quarry", "2517", "load", "4000", "4700", "5", "2", "1"),
    (
        "Paint",
        "Interior Emulsion 20 L",
        "Asian Paints Tractor",
        "3209",
        "nos",
        "3200",
        "3650",
        "18",
        "10",
        "3",
    ),
    ("Paint", "Wall Putty 40 kg", "Birla White", "3214", "bag", "850", "980", "18", "20", "5"),
    ("Tiles", "Vitrified Floor Tile 2x2 ft", "Kajaria", "6907", "sqft", "48", "60", "18", "800", "200"),
    ("Plumbing", "PVC Pipe 1 inch (10 ft)", "Supreme", "3917", "nos", "260", "320", "18", "40", "10"),
    ("Electrical", "Copper Wire 1.5 sq.mm (90 m)", "Finolex", "8544", "nos", "1350", "1550", "18", "15", "5"),
]

QUOTATION_TERMS = """1. Prices are valid for the period mentioned on this quotation.
2. 30% advance along with the work order; balance as per agreed stage payments.
3. Material rates may change if supplier rates change before order confirmation.
4. Any additional work outside this quotation will be charged separately.
5. Water and electricity at site to be provided by the customer.
6. Subject to local jurisdiction."""

INVOICE_TERMS = """1. Payment due within 7 days of invoice date.
2. Interest @18% p.a. may be charged on overdue amounts.
3. Goods once delivered will not be taken back.
4. Subject to local jurisdiction."""


class Command(BaseCommand):
    help = "Seed roles, demo admin user, company settings and sample materials."

    @transaction.atomic
    def handle(self, *args, **options):
        roles = {}
        for code, name, desc in ROLES:
            roles[code], _ = Role.objects.update_or_create(
                code=code, defaults={"name": name, "description": desc}
            )
        self.stdout.write(self.style.SUCCESS(f"Roles: {len(roles)}"))

        username = config("DEMO_ADMIN_USERNAME", default="admin")
        password = config("DEMO_ADMIN_PASSWORD", default="Admin@12345")
        email = config("DEMO_ADMIN_EMAIL", default="admin@akbuilders.local")
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": "AK",
                "last_name": "Admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password(password)
            user.role = roles[Role.SUPER_ADMIN]
            user.must_change_password = True
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Demo admin created: {username} / {password}  (change it after login)")
            )
        else:
            self.stdout.write(f"Admin user '{username}' already exists — password not changed.")

        company = CompanySettings.load()
        if not company.address:
            company.name = "AK Builders"
            company.tagline = "Renovation & Construction"
            company.address = "Main Road"
            company.city = "Thoothukudi"
            company.state = "Tamil Nadu"
            company.state_code = "33"
            company.save()

        cats = {}
        for name, desc in CATEGORIES:
            cats[name], _ = MaterialCategory.objects.get_or_create(name=name, defaults={"description": desc})

        new_items = 0
        today = date.today()
        for cat, name, brand, hsn, unit, pp, sp, gst, stock, reorder in MATERIALS:
            material, created = Material.objects.get_or_create(
                name=name,
                brand=brand,
                defaults=dict(
                    category=cats[cat],
                    hsn_code=hsn,
                    unit=unit,
                    purchase_price=D(pp),
                    selling_price=D(sp),
                    gst_rate=D(gst),
                    reorder_level=D(reorder),
                ),
            )
            if created:
                new_items += 1
                qty = D(stock)
                material.stock_quantity = qty
                material.save(update_fields=["stock_quantity"])
                StockMovement.objects.create(
                    material=material,
                    movement_type=StockMovement.MovementType.OPENING,
                    quantity=qty,
                    balance_after=qty,
                    rate=D(pp),
                    date=today,
                    reference_type="Seed",
                    note="Opening stock (seed data)",
                )
        self.stdout.write(self.style.SUCCESS(f"Categories: {len(cats)}, new materials: {new_items}"))

        TermsTemplate.objects.get_or_create(
            title="Standard quotation terms",
            applies_to=TermsTemplate.AppliesTo.QUOTATION,
            defaults={"content": QUOTATION_TERMS, "is_default": True},
        )
        TermsTemplate.objects.get_or_create(
            title="Standard invoice terms",
            applies_to=TermsTemplate.AppliesTo.INVOICE,
            defaults={"content": INVOICE_TERMS, "is_default": True},
        )
        fy = financial_year(today, company.financial_year_start_month)
        for doc_type, prefix in DEFAULT_PREFIXES.items():
            DocumentSequence.objects.get_or_create(
                doc_type=doc_type, financial_year=fy, defaults={"prefix": prefix}
            )
        self.stdout.write(self.style.SUCCESS(f"Document number series ready for FY {fy}."))
        self.stdout.write(self.style.SUCCESS("Seed data ready."))
