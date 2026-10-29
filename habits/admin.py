from django.contrib import admin

from .models import Goal, Habit, HabitRecord


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "category", "status", "created_by_ai"]
    list_filter = ["category", "status", "created_by_ai"]


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "goal", "frequency", "streak", "difficulty", "is_active"]
    list_filter = ["frequency", "difficulty", "is_active", "created_by_ai"]


@admin.register(HabitRecord)
class HabitRecordAdmin(admin.ModelAdmin):
    list_display = ["habit", "date", "done", "energy", "mood"]
    list_filter = ["done", "failure_reason"]
