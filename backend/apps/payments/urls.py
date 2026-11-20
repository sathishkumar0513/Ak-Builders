from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("advances", views.AdvanceViewSet, basename="advance")
router.register("advance-adjustments", views.AdvanceAdjustmentViewSet, basename="advance-adjustment")
router.register("payments", views.PaymentViewSet, basename="payment")
urlpatterns = router.urls
