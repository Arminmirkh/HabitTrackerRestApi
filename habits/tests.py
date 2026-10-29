from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .models import Goal, Habit, HabitRecord
from .streaks import calculate_streak


def make_user(username="owner", email=None):
    return User.objects.create_user(
        username=username, email=email or f"{username}@example.com", password="TestPass123!"
    )


class GoalOwnershipTests(APITestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.other = make_user("other")
        self.goal = Goal.objects.create(user=self.owner, title="Get fit", category="fitness")
        self.client.force_authenticate(user=self.owner)

    def test_list_only_returns_own_goals(self):
        Goal.objects.create(user=self.other, title="Not mine", category="career")

        response = self.client.get(reverse("goal-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [g["title"] for g in response.data["results"]]
        self.assertEqual(titles, ["Get fit"])

    def test_cannot_retrieve_another_users_goal(self):
        their_goal = Goal.objects.create(user=self.other, title="Private", category="career")

        response = self.client.get(reverse("goal-detail", args=[their_goal.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_another_users_goal(self):
        their_goal = Goal.objects.create(user=self.other, title="Private", category="career")

        response = self.client.delete(reverse("goal-detail", args=[their_goal.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Goal.objects.filter(id=their_goal.id).exists())

    def test_create_assigns_current_user_automatically(self):
        response = self.client.post(
            reverse("goal-list"), {"title": "New goal", "category": "study"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Goal.objects.get(id=response.data["id"]).user, self.owner)


class HabitOwnershipAndValidationTests(APITestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.other = make_user("other")
        self.owner_goal = Goal.objects.create(user=self.owner, title="Get fit", category="fitness")
        self.other_goal = Goal.objects.create(user=self.other, title="Their goal", category="career")
        self.client.force_authenticate(user=self.owner)

    def test_cannot_attach_habit_to_another_users_goal(self):
        response = self.client.post(
            reverse("habit-list"),
            {"title": "Run", "goal": self.other_goal.id, "frequency": "daily"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("goal", response.data)

    def test_can_attach_habit_to_own_goal(self):
        response = self.client.post(
            reverse("habit-list"),
            {"title": "Run", "goal": self.owner_goal.id, "frequency": "daily"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_access_another_users_habit(self):
        their_habit = Habit.objects.create(user=self.other, title="Their habit")

        response = self.client.get(reverse("habit-detail", args=[their_habit.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BulkCreateHabitTests(APITestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.client.force_authenticate(user=self.owner)

    def test_bulk_create_saves_all_valid_items(self):
        payload = [
            {"title": "Drink water", "frequency": "daily"},
            {"title": "Stretch", "frequency": "daily", "difficulty": "easy"},
        ]

        response = self.client.post(reverse("habit-bulk-create"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Habit.objects.filter(user=self.owner).count(), 2)

    def test_bulk_create_is_all_or_nothing(self):
        payload = [
            {"title": "Valid habit", "frequency": "daily"},
            {"title": "", "frequency": "daily"},  # invalid: blank title
        ]

        response = self.client.post(reverse("habit-bulk-create"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Habit.objects.filter(user=self.owner).count(), 0)

    def test_bulk_create_rejects_non_list_body(self):
        response = self.client.post(
            reverse("habit-bulk-create"), {"title": "Not a list"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_create_rejects_more_than_max_items(self):
        payload = [{"title": f"Habit {i}", "frequency": "daily"} for i in range(51)]

        response = self.client.post(reverse("habit-bulk-create"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Habit.objects.filter(user=self.owner).count(), 0)


class CheckInTests(APITestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.habit = Habit.objects.create(user=self.owner, title="Meditate", frequency="daily")
        self.client.force_authenticate(user=self.owner)

    def test_check_in_creates_todays_record(self):
        response = self.client.post(reverse("habit-check-in", args=[self.habit.id]), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        today = timezone.localdate()
        self.assertTrue(HabitRecord.objects.filter(habit=self.habit, date=today, done=True).exists())
        self.assertEqual(response.data["streak"], 1)

    def test_check_in_twice_updates_rather_than_duplicates(self):
        self.client.post(reverse("habit-check-in", args=[self.habit.id]), {"done": True}, format="json")
        self.client.post(
            reverse("habit-check-in", args=[self.habit.id]),
            {"done": False, "note": "changed my mind"},
            format="json",
        )

        today = timezone.localdate()
        self.assertEqual(HabitRecord.objects.filter(habit=self.habit, date=today).count(), 1)
        record = HabitRecord.objects.get(habit=self.habit, date=today)
        self.assertFalse(record.done)
        self.assertEqual(record.note, "changed my mind")

    def test_cannot_check_in_to_another_users_habit(self):
        other = make_user("other")
        their_habit = Habit.objects.create(user=other, title="Not yours", frequency="daily")

        response = self.client.post(
            reverse("habit-check-in", args=[their_habit.id]), {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class StreakCalculationTests(APITestCase):
    """Direct tests of habits.streaks.calculate_streak for the daily case."""

    def setUp(self):
        self.owner = make_user("owner")
        self.habit = Habit.objects.create(user=self.owner, title="Read", frequency="daily")

    def _mark_done(self, days_ago):
        HabitRecord.objects.create(
            habit=self.habit,
            date=timezone.localdate() - timedelta(days=days_ago),
            done=True,
        )

    def test_no_records_gives_zero_streak(self):
        result = calculate_streak(self.habit)

        self.assertEqual(result["current_streak"], 0)
        self.assertEqual(result["longest_streak"], 0)

    def test_consecutive_days_including_today_counts_correctly(self):
        for days_ago in (0, 1, 2):
            self._mark_done(days_ago)

        result = calculate_streak(self.habit)

        self.assertEqual(result["current_streak"], 3)
        self.assertEqual(result["longest_streak"], 3)

    def test_missing_today_does_not_break_streak_but_missing_yesterday_does(self):
        # Done yesterday and the day before, nothing marked yet today --
        # today isn't "missed" until it's over, so the streak should
        # still count as 2.
        self._mark_done(1)
        self._mark_done(2)

        result = calculate_streak(self.habit)

        self.assertEqual(result["current_streak"], 2)

    def test_gap_breaks_current_streak_but_longest_streak_is_preserved(self):
        # A 3-day streak from 5-3 days ago, then a gap, then done today.
        for days_ago in (5, 4, 3):
            self._mark_done(days_ago)
        self._mark_done(0)

        result = calculate_streak(self.habit)

        self.assertEqual(result["current_streak"], 1)
        self.assertEqual(result["longest_streak"], 3)

    def test_deleting_a_record_recalculates_streak(self):
        for days_ago in (0, 1, 2):
            self._mark_done(days_ago)
        self.assertEqual(calculate_streak(self.habit)["current_streak"], 3)

        HabitRecord.objects.filter(habit=self.habit, date=timezone.localdate() - timedelta(days=1)).delete()

        result = calculate_streak(self.habit)
        # Remaining records are "today" and "2 days ago" -- no longer
        # adjacent once "yesterday" is gone, so nothing is consecutive.
        self.assertEqual(result["current_streak"], 1)
        self.assertEqual(result["longest_streak"], 1)


class HabitRecordOwnershipTests(APITestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.other = make_user("other")
        self.habit = Habit.objects.create(user=self.owner, title="Journal", frequency="daily")
        self.their_habit = Habit.objects.create(user=self.other, title="Their habit", frequency="daily")
        self.client.force_authenticate(user=self.owner)

    def test_cannot_create_record_for_another_users_habit(self):
        response = self.client.post(
            reverse("habit-record-list"),
            {"habit": self.their_habit.id, "date": str(timezone.localdate()), "done": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_record_for_same_habit_and_date_is_rejected(self):
        HabitRecord.objects.create(habit=self.habit, date=timezone.localdate(), done=True)

        response = self.client.post(
            reverse("habit-record-list"),
            {"habit": self.habit.id, "date": str(timezone.localdate()), "done": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
