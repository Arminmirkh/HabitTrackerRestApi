from django.utils import timezone
from rest_framework import serializers

from .models import Goal, Habit, HabitRecord
from .streaks import calculate_streak, resync_overall_streak


class GoalSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    habit_count = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = [
            "id", "user", "title", "description", "category",
            "status", "created_by_ai", "habit_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_by_ai", "created_at", "updated_at"]

    def get_habit_count(self, obj) -> int:
        return obj.habits.count()


class HabitSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    goal_title = serializers.SerializerMethodField()
    is_done_today = serializers.SerializerMethodField()
    # streak/best_streak are computed fresh from real HabitRecord history on
    # every read (not just read from the cached DB column) -- previously
    # these were plain model fields, so a habit that simply went unchecked
    # for a day kept showing its old nonzero streak until the *next*
    # check-in happened to trigger a resync. Computing on read fixes that:
    # the very next GET after a missed day already shows 0, no check-in
    # needed. The DB column is still self-healed here too, so it stays a
    # correct cache for anything that reads it directly (e.g. the admin).
    streak = serializers.SerializerMethodField()
    best_streak = serializers.SerializerMethodField()

    class Meta:
        model = Habit
        fields = [
            "id", "goal", "goal_title", "user", "title", "description",
            "frequency", "daily_goal", "streak", "best_streak", "streak_goal",
            "difficulty", "unit", "reminder_time", "is_active", "is_done_today",
            "created_by_ai", "created_at", "updated_at",
        ]
        read_only_fields = ["created_by_ai", "created_at", "updated_at"]

    def validate_goal(self, goal):
        request = self.context["request"]
        if goal.user_id != request.user.id:
            raise serializers.ValidationError("You do not own this goal.")
        return goal

    def get_goal_title(self, obj) -> str | None:
        return obj.goal.title if obj.goal_id else None

    def get_is_done_today(self, obj) -> bool:
        today = timezone.localdate()
        # Uses obj.records.all() so it benefits from prefetch_related("records")
        # on the queryset instead of firing a query per habit.
        return any(r.date == today and r.done for r in obj.records.all())

    def _live_streak(self, obj):
        # Cache per-instance so get_streak/get_best_streak (and repeated
        # calls within one serialization) don't each recompute/query twice.
        if not hasattr(obj, "_streak_result_cache"):
            obj._streak_result_cache = calculate_streak(obj)
        return obj._streak_result_cache

    def get_streak(self, obj) -> int:
        result = self._live_streak(obj)
        if obj.streak != result["current_streak"]:
            Habit.objects.filter(pk=obj.pk).update(streak=result["current_streak"])
            obj.streak = result["current_streak"]
        return result["current_streak"]

    def get_best_streak(self, obj) -> int:
        result = self._live_streak(obj)
        if obj.best_streak != result["longest_streak"]:
            Habit.objects.filter(pk=obj.pk).update(best_streak=result["longest_streak"])
            obj.best_streak = result["longest_streak"]
        return result["longest_streak"]


class HabitRecordSerializer(serializers.ModelSerializer):
    habit_title = serializers.CharField(source="habit.title", read_only=True)

    class Meta:
        model = HabitRecord
        fields = [
            "id", "habit", "habit_title", "date", "done", "completed_at",
            "energy", "mood", "failure_reason", "note", "created_at",
        ]
        read_only_fields = ["completed_at", "created_at"]

    def validate_habit(self, habit):
        request = self.context["request"]
        if habit.user_id != request.user.id:
            raise serializers.ValidationError("You do not own this habit.")
        return habit

    def validate(self, attrs):
        habit = attrs.get("habit") or getattr(self.instance, "habit", None)
        date = attrs.get("date") or getattr(self.instance, "date", None)
        if habit and date:
            qs = HabitRecord.objects.filter(habit=habit, date=date)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "A record for this habit and date already exists."
                )
        return attrs

    def _resync_streak(self, habit):
        # Always recompute from real HabitRecord history (see streaks.py)
        # rather than incrementing/resetting a counter -- keeps the cached
        # Habit.streak (and Habit.best_streak) correct even after backdating
        # or editing a record. Runs on every create/update of a HabitRecord,
        # so there's no need for a separate "refresh the streak" endpoint --
        # it's always current by the time the client reads the habit back.
        habit.refresh_from_db(fields=["streak", "best_streak"])  # avoid stale in-memory values
        result = calculate_streak(habit)
        update_fields = []
        if habit.streak != result["current_streak"]:
            habit.streak = result["current_streak"]
            update_fields.append("streak")
        if habit.best_streak != result["longest_streak"]:
            habit.best_streak = result["longest_streak"]
            update_fields.append("best_streak")
        if update_fields:
            habit.save(update_fields=update_fields)

    def create(self, validated_data):
        if validated_data.get("done"):
            validated_data["completed_at"] = timezone.now()
        record = super().create(validated_data)
        self._resync_streak(record.habit)
        resync_overall_streak(record.habit.user)
        return record

    def update(self, instance, validated_data):
        if validated_data.get("done") and not instance.completed_at:
            validated_data["completed_at"] = timezone.now()
        elif "done" in validated_data and not validated_data["done"]:
            validated_data["completed_at"] = None
        record = super().update(instance, validated_data)
        self._resync_streak(record.habit)
        resync_overall_streak(record.habit.user)
        return record
