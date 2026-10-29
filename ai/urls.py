from django.urls import path

from .views import GenerateHabitsView

urlpatterns = [
    path("ai/generate-habits/", GenerateHabitsView.as_view(), name="generate-habits"),
]
