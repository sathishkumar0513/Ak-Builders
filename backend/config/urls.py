from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

admin.site.site_header = "AK Builders Administration"
admin.site.site_title = "AK Builders"

api_v1 = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.customers.urls")),
    path("", include("apps.materials.urls")),
    path("", include("apps.suppliers.urls")),
    path("", include("apps.quotations.urls")),
    path("", include("apps.projects.urls")),
    path("", include("apps.invoices.urls")),
    path("", include("apps.payments.urls")),
    path("", include("apps.expenses.urls")),
    path("", include("apps.reports.urls")),
]

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
