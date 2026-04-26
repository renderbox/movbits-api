from rest_framework.routers import DefaultRouter

from .views import FeatureFlagViewSet

router = DefaultRouter()
router.register("features", FeatureFlagViewSet, basename="feature-flags")

urlpatterns = router.urls
