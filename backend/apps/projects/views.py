from django.db.models import Prefetch
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.permissions import ALL_ROLES, FINANCE, MANAGEMENT, SITE_TEAM, RoleBasedPermission
from apps.core.exceptions import BusinessRuleError
from apps.core.mixins import SoftDeleteViewSetMixin
from apps.core.uploads import validate_image_upload

from . import services
from .models import PaymentStage, ProgressNote, Project, ProjectMaterialIssue
from .serializers import (
    MaterialIssueSerializer,
    ProgressNoteSerializer,
    ProjectListSerializer,
    ProjectSerializer,
    StagesSerializer,
)


class ProjectFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=Project.Status.choices)

    class Meta:
        model = Project
        fields = ["status", "customer", "assigned_engineer", "project_type"]


@extend_schema(tags=["Projects"])
class ProjectViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet):
    """Projects / sites. Site engineers see only projects assigned to them."""

    permission_classes = [RoleBasedPermission]
    allowed_roles = {
        "read": ALL_ROLES,
        "write": MANAGEMENT,
        "destroy": MANAGEMENT,
        "restore": MANAGEMENT,
        "summary": FINANCE,
        "set_stages": MANAGEMENT,
        "materials": ALL_ROLES,
        "issue_material": SITE_TEAM,
        "undo_issue": MANAGEMENT,
        "progress": ALL_ROLES,
        "add_progress": SITE_TEAM,
        "set_status": SITE_TEAM,
    }
    filterset_class = ProjectFilter
    search_fields = ["code", "name", "customer__name", "customer__phone", "site_address", "site_city"]
    ordering_fields = [
        "code",
        "name",
        "start_date",
        "expected_end_date",
        "contract_value",
        "progress_percent",
        "created_at",
    ]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "delete"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = Project.objects.select_related("customer", "assigned_engineer", "quotation")
        if self.action != "list":
            qs = qs.prefetch_related(
                Prefetch("payment_stages", queryset=PaymentStage.objects.order_by("sort_order"))
            )
        return services.visible_projects_for(self.request.user, qs)

    def get_serializer_class(self):
        return ProjectListSerializer if self.action == "list" else ProjectSerializer

    def _detail(self, pk, code=200):
        return Response(
            ProjectSerializer(self.get_queryset().get(pk=pk), context=self.get_serializer_context()).data,
            status=code,
        )

    def create(self, request, *args, **kwargs):
        s = ProjectSerializer(data=request.data, context=self.get_serializer_context())
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        stages = data.pop("stages", None)
        p = services.create_project(data=data, stages=stages)
        return self._detail(p.pk, status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        p = self.get_object()
        s = ProjectSerializer(p, data=request.data, partial=True, context=self.get_serializer_context())
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        data.pop("stages", None)
        services.update_project(project=p, data=data)
        return self._detail(p.pk)

    def perform_destroy(self, instance):
        if instance.invoices.exists() or instance.payments.exists() or instance.material_issues.exists():
            raise BusinessRuleError(
                "This project has invoices, payments or material entries. Mark it Cancelled instead."
            )
        instance.soft_delete(self.request.user)

    @extend_schema(responses={200: OpenApiResponse(description="Money summary")})
    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """Contract value vs cost vs billed vs received."""
        return Response(services.project_summary(self.get_object()))

    @extend_schema(request=StagesSerializer, responses=ProjectSerializer)
    @action(detail=True, methods=["post"], url_path="stages")
    def set_stages(self, request, pk=None):
        s = StagesSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.set_stages(project=self.get_object(), stages=s.validated_data["stages"])
        return self._detail(pk)

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {"status": {"type": "string"}, "progress_percent": {"type": "number"}},
            }
        }
    )
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        """Site team can move the project status / progress without editing money fields."""
        p = self.get_object()
        data = {}
        if request.data.get("status"):
            if request.data["status"] not in Project.Status.values:
                raise BusinessRuleError("Unknown status.", field="status")
            if (
                request.data["status"] == Project.Status.CANCELLED
                and request.user.role_code not in MANAGEMENT
            ):
                raise BusinessRuleError("Only an Admin can cancel a project.", field="status")
            data["status"] = request.data["status"]
        if request.data.get("progress_percent") not in (None, ""):
            data["progress_percent"] = request.data["progress_percent"]
        services.update_project(project=p, data=data)
        return self._detail(pk)

    # ---- site material ----
    @extend_schema(responses=MaterialIssueSerializer(many=True))
    @action(detail=True, methods=["get"])
    def materials(self, request, pk=None):
        p = self.get_object()
        issues = ProjectMaterialIssue.objects.filter(project=p).select_related("material", "issued_by")
        data = {
            "entries": MaterialIssueSerializer(issues, many=True, context=self.get_serializer_context()).data,
            "summary": services.site_material_summary(p),
        }
        from apps.materials.serializers import can_see_cost

        if not can_see_cost(request):
            for row in data["summary"]:
                row.pop("cost", None)
        return Response(data)

    @extend_schema(request=MaterialIssueSerializer, responses=MaterialIssueSerializer)
    @action(detail=True, methods=["post"], url_path="issue-material")
    def issue_material(self, request, pk=None):
        """Issue material to site (stock −) or return it (is_return=true, stock +)."""
        p = self.get_object()
        s = MaterialIssueSerializer(data=request.data, context=self.get_serializer_context())
        s.is_valid(raise_exception=True)
        d = s.validated_data
        issue = services.issue_material(
            project=p,
            material=d["material"],
            quantity=d["quantity"],
            issue_date=d.get("issue_date"),
            is_return=d.get("is_return", False),
            notes=d.get("notes", ""),
            received_by_name=d.get("received_by_name", ""),
            vehicle_number=d.get("vehicle_number", ""),
            issued_by=request.user,
        )
        return Response(
            MaterialIssueSerializer(issue, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"], url_path=r"materials/(?P<issue_id>\d+)")
    def undo_issue(self, request, pk=None, issue_id=None):
        """Remove a wrong material entry (reverses the stock movement)."""
        issue = ProjectMaterialIssue.objects.filter(project=self.get_object(), pk=issue_id).first()
        if not issue:
            raise BusinessRuleError("Entry not found.")
        services.undo_issue(issue=issue)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ---- progress ----
    @extend_schema(responses=ProgressNoteSerializer(many=True))
    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        notes = (
            ProgressNote.objects.filter(project=self.get_object())
            .prefetch_related("photos")
            .select_related("created_by")
        )
        return Response(ProgressNoteSerializer(notes, many=True).data)

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "note": {"type": "string"},
                    "date": {"type": "string"},
                    "progress_percent": {"type": "number"},
                    "workers_on_site": {"type": "integer"},
                    "photos": {"type": "array", "items": {"type": "string", "format": "binary"}},
                },
            }
        },
        responses=ProgressNoteSerializer,
    )
    @action(detail=True, methods=["post"], url_path="add-progress")
    def add_progress(self, request, pk=None):
        """Daily site note with up to 10 photos (multipart, field 'photos')."""
        p = self.get_object()
        s = ProgressNoteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        photos = request.FILES.getlist("photos")
        if len(photos) > 10:
            raise BusinessRuleError("Upload at most 10 photos at a time.", field="photos")
        for f in photos:
            validate_image_upload(f, field="photos")
        note = services.add_progress(
            project=p,
            note=s.validated_data["note"],
            on=s.validated_data.get("date"),
            progress_percent=s.validated_data.get("progress_percent"),
            workers_on_site=s.validated_data.get("workers_on_site"),
            photos=photos,
        )
        return Response(ProgressNoteSerializer(note).data, status=status.HTTP_201_CREATED)
