import calendar
from datetime import date

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Goal, Habit, HabitRecord
from .serializers import GoalSerializer, HabitRecordSerializer, HabitSerializer
from .streaks import calculate_overall_streak, calculate_streak, resync_overall_streak

MAX_BULK_HABITS = 50


class GoalViewSet(viewsets.ModelViewSet):
    """
    Supports ?status=active|completed|paused and ?category=<choice>
    for the Flutter client's goal filters/tabs.
    """
    serializer_class = GoalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Goal.objects.filter(user=self.request.user)
        status_param = self.request.query_params.get("status")
        category = self.request.query_params.get("category")
        if status_param:
            qs = qs.filter(status=status_param)
        if category:
            qs = qs.filter(category=category)
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class HabitViewSet(viewsets.ModelViewSet):
    """
    Supports ?goal=<id>, ?is_active=true|false and ?frequency=<choice>
    for filtering the habit list screen.
    """
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Habit.objects.filter(user=self.request.user).prefetch_related("records")
        goal_id = self.request.query_params.get("goal")
        is_active = self.request.query_params.get("is_active")
        frequency = self.request.query_params.get("frequency")
        if goal_id:
            qs = qs.filter(goal_id=goal_id)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("1", "true", "yes"))
        if frequency:
            qs = qs.filter(frequency=frequency)
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        """
        POST /api/habits/bulk-create/
        Body: a JSON list of habit objects, e.g.

        [
            {"goal": 3, "title": "Drink water", "frequency": "daily"},
            {"goal": 3, "title": "Stretch", "frequency": "daily", "difficulty": "easy"}
        ]

        Validates every item (including that each "goal" belongs to
        the caller) before creating any of them -- if one item is
        invalid, nothing is saved and the response lists the errors
        per index so the client can show which entries failed.
        """
        if not isinstance(request.data, list):
            return Response(
                {"error": "Expected a JSON list of habit objects."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.data:
            return Response(
                {"error": "The list of habits must not be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(request.data) > MAX_BULK_HABITS:
            return Response(
                {"error": f"Cannot create more than {MAX_BULK_HABITS} habits at once."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = HabitSerializer(data=request.data, many=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, pk=None):
        """
        POST /api/habits/{id}/check-in/
        Body (all optional): {"done": true, "note": "...", "energy": 4, "mood": 5}

        Convenience endpoint for the mobile client: marks *today's*
        record for this habit done/not done, creating it if it
        doesn't exist yet, and updates the habit's streak -- without
        the client needing to know today's date or juggle the
        habit-records endpoint directly.
        """
        habit = self.get_object()
        today = timezone.localdate()
        payload = {
            "done": request.data.get("done", True),
            "note": request.data.get("note", ""),
            "energy": request.data.get("energy"),
            "mood": request.data.get("mood"),
        }

        instance = HabitRecord.objects.filter(habit=habit, date=today).first()
        if instance:
            serializer = HabitRecordSerializer(
                instance, data=payload, partial=True, context={"request": request}
            )
        else:
            payload.update({"habit": habit.id, "date": today})
            serializer = HabitRecordSerializer(data=payload, context={"request": request})

        serializer.is_valid(raise_exception=True)
        serializer.save()
        # The record's serializer resyncs streak/best_streak on the Habit
        # instance it loaded internally, not on this `habit` reference --
        # refresh so the response reflects the just-updated values.
        habit.refresh_from_db(fields=["streak", "best_streak"])
        return Response(HabitSerializer(habit, context={"request": request}).data)

    @action(detail=False, methods=["get"], url_path="overall-streak")
    def overall_streak(self, request):
        """
        GET /api/habits/overall-streak/

        Cross-habit streak: how many consecutive days the user has
        completed AT LEAST ONE of their habits (any habit), regardless
        of that habit's own frequency -- distinct from any single
        habit's own streak/best_streak.
        """
        result = calculate_overall_streak(request.user)
        resync_overall_streak(request.user)
        return Response({
            "current_streak": result["current_streak"],
            "longest_streak": result["longest_streak"],
            "unit": result["unit"],
        })

    @action(detail=False, methods=["get"], url_path="analytics/streak")
    def analytics_streak(self, request):
        """
        GET /api/habits/analytics/streak/?year=YYYY&month=MM

        Returns one entry per day of the given month:
        {"date": "YYYY-MM-DD", "total_habits": int, "completed_habits": int}

        - total_habits: how many of the user's habits were active on
          that day (created on/before that date and not yet deleted).
        - completed_habits: how many of those had a done HabitRecord
          for that date.

        Powers the client's monthly streak/calendar heatmap -- this
        is a read-only aggregate and does not touch Habit.streak or
        Habit.best_streak (those stay in sync via check-in/records).
        """
        today = timezone.localdate()
        try:
            year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            return Response(
                {"error": "year and month must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (1 <= month <= 12):
            return Response(
                {"error": "month must be between 1 and 12."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        habits = list(
            Habit.objects.filter(user=request.user).only("id", "created_at")
        )
        days_in_month = calendar.monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end = date(year, month, days_in_month)

        done_by_day = {}
        for habit_id, record_date in HabitRecord.objects.filter(
            habit__user=request.user,
            done=True,
            date__gte=month_start,
            date__lte=month_end,
        ).values_list("habit_id", "date"):
            done_by_day.setdefault(record_date, set()).add(habit_id)

        results = []
        for day_num in range(1, days_in_month + 1):
            current = date(year, month, day_num)
            total_habits = sum(
                1 for h in habits if h.created_at.date() <= current
            )
            completed_habits = len(done_by_day.get(current, set()))
            results.append({
                "date": current.isoformat(),
                "total_habits": total_habits,
                "completed_habits": completed_habits,
            })

        return Response(results)


class HabitRecordViewSet(viewsets.ModelViewSet):
    """
    Supports ?habit=<id>, ?date=YYYY-MM-DD and ?date_from=/?date_to=
    for the mobile client's history/calendar views.
    """
    serializer_class = HabitRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = HabitRecord.objects.filter(habit__user=self.request.user)
        habit_id = self.request.query_params.get("habit")
        date = self.request.query_params.get("date")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if habit_id:
            qs = qs.filter(habit_id=habit_id)
        if date:
            qs = qs.filter(date=date)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs

    def perform_destroy(self, instance):
        habit = instance.habit
        user = habit.user
        instance.delete()
        # Deleting a done record can change the streak (e.g. removing
        # a backdated entry) -- resync the cached fields from real data.
        # (This is a best-effort cache refresh for direct DB readers like
        # the admin; HabitSerializer itself always computes fresh anyway.)
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
        resync_overall_streak(user)
