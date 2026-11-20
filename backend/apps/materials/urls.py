from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("material-categories", views.MaterialCategoryViewSet, basename="material-category")
router.register("materials", views.MaterialViewSet, basename="material")
router.register("stock-movements", views.StockMovementViewSet, basename="stock-movement")
urlpatterns = router.urls
