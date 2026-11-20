from datetime import date
from decimal import Decimal

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import ALL_ROLES, FINANCE, RoleBasedPermission
from apps.core.audit import log_action
from apps.core.exceptions import BusinessRuleError

from . import exporters
from .dashboard import dashboard
from .services import REPORTS, run_report

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ID_PARAMS = ("customer", "project", "supplier", "material", "category")
TEXT_PARAMS = ("mode", "status", "group")
BOOL_PARAMS = ("only_due", "low_only")


def _json(v):
    """Decimals → strings (exact money), dates → ISO, recursively."""
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _json(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json(x) for x in v]
    return v


def _parse_date(raw, field):
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise BusinessRuleError("Enter a valid date (YYYY-MM-DD).", field=field) from exc


class ExportThrottle(ScopedRateThrottle):
    """Excel/PDF building is heavy: limit downloads per user. Screen views are not affected."""

    scope_attr = "export_throttle_scope"

    def allow_request(self, request, view):
        if request.query_params.get("export") not in ("xlsx", "pdf"):
            return True
        return super().allow_request(request, view)


@extend_schema(tags=["Dashboard"], responses=OpenApiTypes.OBJECT)
class DashboardView(APIView):
    """Cards, charts and short lists for the home page. Money figures only for Accountant and above."""

    permission_classes = [RoleBasedPermission]
    allowed_roles = ALL_ROLES

    def get(self, request):
        return Response(_json(dashboard(request.user)))


class ReportListView(APIView):
    """The available reports and the filters each one takes."""

    permission_classes = [RoleBasedPermission]
    allowed_roles = FINANCE

    @extend_schema(tags=["Reports"], responses=OpenApiTypes.OBJECT, operation_id="reports_list")
    def get(self, request):
        return Response(
            [
                {
                    "key": k,
                    "title": v["title"],
                    "group": v["group"],
                    "description": v["description"],
                    "filters": v["filters"],
                }
                for k, v in REPORTS.items()
            ]
        )


class ReportView(APIView):
    """Run a report. Same filters for screen, Excel (?export=xlsx) and PDF (?export=pdf)."""

    permission_classes = [RoleBasedPermission]
    allowed_roles = FINANCE
    throttle_classes = [*APIView.throttle_classes, ExportThrottle]
    export_throttle_scope = "export"

    @extend_schema(
        tags=["Reports"],
        operation_id="reports_run",
        responses=OpenApiTypes.OBJECT,
        parameters=[
            OpenApiParameter("date_from", OpenApiTypes.DATE, description="Default: start of financial year"),
            OpenApiParameter("date_to", OpenApiTypes.DATE, description="Default: today"),
            OpenApiParameter("export", str, enum=["xlsx", "pdf"], description="Download instead of JSON"),
            *[OpenApiParameter(p, int) for p in ID_PARAMS],
            *[OpenApiParameter(p, str) for p in TEXT_PARAMS],
            *[OpenApiParameter(p, bool) for p in BOOL_PARAMS],
        ],
    )
    def get(self, request, key):
        q = request.query_params
        params = {}
        for f in ("date_from", "date_to"):
            if q.get(f):
                params[f] = _parse_date(q[f], f)
        for f in ID_PARAMS:
            if q.get(f):
                if not q[f].isdigit():
                    raise BusinessRuleError("Invalid value.", field=f)
                params[f] = int(q[f])
        for f in TEXT_PARAMS:
            if q.get(f):
                params[f] = q[f][:30]
        for f in BOOL_PARAMS:
            params[f] = q.get(f) in ("1", "true", "yes")

        report = run_report(key, params, request.user)
        export = q.get("export")
        if export in ("xlsx", "pdf"):
            content = exporters.to_xlsx(report) if export == "xlsx" else exporters.to_pdf(report)
            log_action(
                "EXPORT", model_name="Report", object_repr=f"{report['title']} ({export})", user=request.user
            )
            resp = HttpResponse(content, content_type=XLSX if export == "xlsx" else "application/pdf")
            resp["Content-Disposition"] = f'attachment; filename="{exporters.filename(report, export)}"'
            return resp
        return Response(_json(report))
