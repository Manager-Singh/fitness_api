# nutration/urls.py
from django.urls import path, include
from rest_framework.routers import SimpleRouter   # simple → no trailing “/”

from .views import (
    AgeGroupViewSet, FoodViewSet,
    ModuleViewSet, ModuleFoodViewSet, MyPlanView
)
from .views_log import NutraLogViewSet             # ← daily log (NutraSession)

# -------------------------------------------------------------------
# router: all CRUD / read-only sets
# -------------------------------------------------------------------
router = SimpleRouter(trailing_slash=False)
router.register("age-groups",   AgeGroupViewSet)
router.register("foods",        FoodViewSet)
router.register("modules",      ModuleViewSet)
router.register("module-foods", ModuleFoodViewSet)
router.register("nutra-logs",   NutraLogViewSet, basename="nutra-log")  # NEW

# -------------------------------------------------------------------
# urlpatterns
# -------------------------------------------------------------------
urlpatterns = [
    # personalised plan (GET)
    path("my-nutrition-plan", MyPlanView.as_view(), name="my-nutrition-plan"),
    # everything registered above
    path("", include(router.urls)),
]
