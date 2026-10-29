"""
Seeds the database with a handful of demo users, each with realistic
goals, habits, and weeks of check-in history -- useful for demoing
the app or testing the Flutter client against non-empty data.

Usage:
    python manage.py seed_data
    python manage.py seed_data --days 90
    python manage.py seed_data --flush        # wipe previous demo data first
    python manage.py seed_data --seed 42       # reproducible output
"""
import random
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from habits.models import Goal, Habit, HabitRecord
from habits.streaks import calculate_streak

DEMO_PASSWORD = "DemoPass123!"

DEMO_USERS = [
    {"username": "demo_alice", "email": "alice.demo@example.com", "first_name": "Alice", "last_name": "Nguyen", "age": 27, "gender": "F"},
    {"username": "demo_bob", "email": "bob.demo@example.com", "first_name": "Bob", "last_name": "Carter", "age": 34, "gender": "M"},
    {"username": "demo_carla", "email": "carla.demo@example.com", "first_name": "Carla", "last_name": "Reyes", "age": 22, "gender": "F"},
]

GOALS_BY_CATEGORY = {
    "fitness": [
        ("Run a 10k", "Build up endurance to comfortably run 10 kilometers."),
        ("Get stronger", "Increase overall strength with consistent training."),
    ],
    "health": [
        ("Sleep better", "Establish a consistent, restful sleep schedule."),
        ("Eat healthier", "Cut down on processed food and eat more balanced meals."),
    ],
    "study": [
        ("Learn Spanish", "Reach conversational fluency in Spanish."),
        ("Finish the certification", "Complete the online certification course."),
    ],
    "career": [
        ("Improve public speaking", "Get more comfortable presenting to groups."),
        ("Build a portfolio", "Put together a portfolio of past projects."),
    ],
    "finance": [
        ("Save an emergency fund", "Build up three months of living expenses in savings."),
        ("Track spending", "Get a clear picture of where money goes each month."),
    ],
}

# (habit title, frequency, daily_goal, difficulty)
HABITS_BY_GOAL_TITLE = {
    "Run a 10k": [
        ("Go for a run", "daily", 4, "medium"),
        ("Stretch after running", "daily", 5, "easy"),
        ("Long run", "weekly", 1, "hard"),
    ],
    "Get stronger": [
        ("Strength training session", "weekly", 3, "medium"),
        ("Track protein intake", "daily", 6, "easy"),
    ],
    "Sleep better": [
        ("Lights out by 11pm", "daily", 5, "medium"),
        ("No screens before bed", "daily", 4, "medium"),
    ],
    "Eat healthier": [
        ("Cook a home meal", "daily", 5, "easy"),
        ("Meal prep for the week", "weekly", 1, "medium"),
    ],
    "Learn Spanish": [
        ("Do a language lesson", "daily", 6, "easy"),
        ("Watch a show in Spanish", "weekly", 2, "easy"),
    ],
    "Finish the certification": [
        ("Study a module", "daily", 5, "medium"),
        ("Take a practice quiz", "weekly", 1, "medium"),
    ],
    "Improve public speaking": [
        ("Practice out loud", "daily", 4, "medium"),
        ("Record a practice talk", "weekly", 1, "hard"),
    ],
    "Build a portfolio": [
        ("Work on a project", "daily", 4, "medium"),
        ("Publish an update", "weekly", 1, "medium"),
    ],
    "Save an emergency fund": [
        ("Log today's spending", "daily", 6, "easy"),
        ("Transfer to savings", "weekly", 1, "easy"),
        ("Review budget", "monthly", 1, "medium"),
    ],
    "Track spending": [
        ("Log today's spending", "daily", 6, "easy"),
        ("Review budget", "monthly", 1, "medium"),
    ],
}

FAILURE_REASONS = ["forgot", "busy", "tired", "sick", "no_motivation", "other"]
NOTES_DONE = ["Felt great", "Tougher than expected but got it done", "Quick one today", "", "", ""]
NOTES_MISSED = ["Ran out of time", "Just wasn't feeling it", "", ""]
REMINDER_TIMES = [time(7, 0), time(8, 30), time(12, 0), time(18, 0), time(21, 0), None]


class Command(BaseCommand):
    help = "Seed the database with random but realistic demo users, goals, habits, and history."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=60, help="Days of history per habit (default 60).")
        parser.add_argument("--flush", action="store_true", help="Delete previously seeded demo_* users first.")
        parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output.")

    def handle(self, *args, **options):
        if options["seed"] is not None:
            random.seed(options["seed"])

        if options["flush"]:
            deleted, _ = User.objects.filter(
                username__in=[u["username"] for u in DEMO_USERS]
            ).delete()
            self.stdout.write(self.style.WARNING(f"Removed {deleted} existing demo objects."))

        days = options["days"]

        with transaction.atomic():
            for user_data in DEMO_USERS:
                user = self._get_or_create_user(user_data)
                self._seed_for_user(user, days)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(DEMO_USERS)} demo users with goals, habits, and {days} days of history."
        ))
        self.stdout.write(f"Password for all seeded users: {DEMO_PASSWORD}")
        for u in DEMO_USERS:
            self.stdout.write(f"  - {u['email']}")

    def _get_or_create_user(self, data):
        user, created = User.objects.get_or_create(
            username=data["username"],
            defaults={
                "email": data["email"],
                "first_name": data["first_name"],
                "last_name": data["last_name"],
                "age": data["age"],
                "gender": data["gender"],
            },
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        return user

    def _seed_for_user(self, user, days):
        categories = random.sample(list(GOALS_BY_CATEGORY.keys()), k=random.randint(2, 3))
        for category in categories:
            title, description = random.choice(GOALS_BY_CATEGORY[category])
            goal, _ = Goal.objects.get_or_create(
                user=user,
                title=title,
                defaults={
                    "description": description,
                    "category": category,
                    "status": random.choice(["active", "active", "active", "paused"]),
                },
            )

            for habit_title, frequency, daily_goal, difficulty in HABITS_BY_GOAL_TITLE.get(title, []):
                habit, created = Habit.objects.get_or_create(
                    user=user,
                    goal=goal,
                    title=habit_title,
                    defaults={
                        "frequency": frequency,
                        "daily_goal": daily_goal,
                        "streak_goal": random.choice([7, 14, 21, 30]),
                        "difficulty": difficulty,
                        "reminder_time": random.choice(REMINDER_TIMES),
                        "is_active": True,
                    },
                )
                if created:
                    self._seed_records(habit, days)
                    result = calculate_streak(habit)
                    habit.streak = result["current_streak"]
                    habit.best_streak = result["longest_streak"]
                    habit.save(update_fields=["streak", "best_streak"])

        from habits.streaks import resync_overall_streak  # absolute import: this module lives under habits.management.commands
        resync_overall_streak(user)

    def _seed_records(self, habit, days):
        today = timezone.localdate()
        base_rate = {"easy": 0.85, "medium": 0.7, "hard": 0.55}[habit.difficulty]

        # weekly/monthly attempt frequency is now independent of daily_goal
        # (a per-day quantity target, not a per-period attempt count) --
        # just pick a plausible fixed cadence for demo data.
        monthly_days = None
        if habit.frequency == "monthly":
            monthly_days = sorted(random.sample(range(1, 29), k=random.randint(1, 3)))

        records = []
        for i in range(days, -1, -1):
            day = today - timedelta(days=i)

            if habit.frequency == "daily":
                should_attempt = True
            elif habit.frequency == "weekly":
                should_attempt = random.random() < (2 / 7)
            else:
                should_attempt = day.day in monthly_days

            if not should_attempt:
                continue

            done = random.random() < base_rate
            # Give the most recent week a livelier streak for demo purposes.
            if i <= 5 and habit.difficulty != "hard":
                done = random.random() < 0.9

            completed_at = None
            if done:
                completed_at = timezone.make_aware(
                    datetime.combine(day, time(hour=random.randint(6, 22)))
                )

            records.append(HabitRecord(
                habit=habit,
                date=day,
                done=done,
                completed_at=completed_at,
                energy=random.randint(3, 5) if done else random.randint(1, 3),
                mood=random.randint(3, 5) if done else random.randint(1, 4),
                failure_reason="" if done else random.choice(FAILURE_REASONS),
                note=random.choice(NOTES_DONE) if done else random.choice(NOTES_MISSED),
            ))

        HabitRecord.objects.bulk_create(records, ignore_conflicts=True)
