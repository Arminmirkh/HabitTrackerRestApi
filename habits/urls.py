from rest_framework.routers import DefaultRouter

from .views import GoalViewSet, HabitRecordViewSet, HabitViewSet

router = DefaultRouter()
router.register(r"goals", GoalViewSet, basename="goal")
router.register(r"habits", HabitViewSet, basename="habit")
router.register(r"habit-records", HabitRecordViewSet, basename="habit-record")

urlpatterns = router.urls
