from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("audit-logs", views.AuditLogViewSet, basename="audit-log")
router.register("settings/sequences", views.DocumentSequenceViewSet, basename="sequence")
router.register("settings/terms", views.TermsTemplateViewSet, basename="terms")

urlpatterns = [
    path("health/", views.health, name="health"),
    path("lookups/", views.lookups, name="lookups"),
    path("lookups/cities/", views.city_suggestions, name="city-suggestions"),
    path("settings/company/", views.CompanySettingsView.as_view(), name="company-settings"),
] + router.urls
