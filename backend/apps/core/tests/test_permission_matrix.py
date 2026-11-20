"""
Role × endpoint sweep.

1. Every GET list endpoint in the API schema is called as every role: it must answer 200 or 403,
   never 500, and anonymous users always get 401.
2. The answer must match the access table in the README (who may see what).
"""

import pytest
from drf_spectacular.generators import SchemaGenerator

from apps.accounts.models import Role

pytestmark = pytest.mark.django_db

SA, AD, AC, SE, SL = Role.SUPER_ADMIN, Role.ADMIN, Role.ACCOUNTANT, Role.SITE_ENGINEER, Role.SALES
ALL = {SA, AD, AC, SE, SL}
MANAGEMENT = {SA, AD}
FINANCE = {SA, AD, AC}
SALES_UP = {SA, AD, AC, SL}

# path prefix (after /api/v1/) → roles that may read it. First match wins.
EXPECTED = [
    ("dashboard/", ALL),
    ("health/", ALL),
    ("lookups/", ALL),
    ("auth/me/", ALL),
    ("users/lookup/", ALL),
    ("users/", MANAGEMENT),
    ("roles/", MANAGEMENT),
    ("audit-logs/", MANAGEMENT),
    ("settings/company/", ALL),
    ("settings/sequences/", MANAGEMENT),
    ("settings/terms/", SALES_UP),
    ("customers/", SALES_UP),
    ("materials/", ALL),
    ("material-categories/", ALL),
    ("stock-movements/", ALL),
    ("suppliers/", FINANCE),
    ("purchases/", FINANCE),
    ("supplier-payments/", FINANCE),
    ("quotations/", SALES_UP),
    ("projects/", ALL),
    ("invoices/", FINANCE),
    ("advances/", FINANCE),
    ("advance-adjustments/", FINANCE),
    ("payments/", FINANCE),
    ("expenses/", FINANCE | {SE}),
    ("reports/", FINANCE),
]


def _list_endpoints():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    return sorted(
        p for p, ops in schema["paths"].items() if "get" in ops and "{" not in p and p.startswith("/api/v1/")
    )


def _expected(path):
    rel = path.removeprefix("/api/v1/")
    for prefix, roles in EXPECTED:
        if rel.startswith(prefix):
            return roles
    return None


def test_every_list_endpoint_is_covered_by_the_table():
    missing = [p for p in _list_endpoints() if _expected(p) is None]
    assert not missing, f"Add these endpoints to EXPECTED: {missing}"


@pytest.mark.parametrize("role", sorted(ALL))
def test_role_access_matches_table(auth_client, role):
    client, _ = auth_client(role)
    wrong, errors = [], []
    for path in _list_endpoints():
        if path.endswith("/ledger/") or "{" in path:
            continue
        r = client.get(path)
        if r.status_code >= 500:
            errors.append((path, r.status_code))
            continue
        allowed = role in _expected(path)
        # 400 = got past the permission check but needs a parameter (e.g. invoices/prefill/)
        ok = r.status_code in (200, 400) if allowed else r.status_code == 403
        if not ok:
            wrong.append((path, r.status_code, "should allow" if allowed else "should deny"))
    assert not errors, errors
    assert not wrong, wrong


def test_anonymous_gets_401_everywhere_except_health(api):
    for path in _list_endpoints():
        r = api.get(path)
        if path.endswith("/health/"):
            assert r.status_code == 200
        else:
            assert r.status_code == 401, (path, r.status_code)
