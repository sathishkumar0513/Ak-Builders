from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("suppliers", views.SupplierViewSet, basename="supplier")
router.register("purchases", views.PurchaseViewSet, basename="purchase")
router.register("supplier-payments", views.SupplierPaymentViewSet, basename="supplier-payment")
urlpatterns = router.urls
