from django.db import models
from accounts.models import User


class Goal(models.Model):

    CATEGORY_CHOICES = [
        ("fitness", "Fitness"),
        ("health", "Health"),
        ("study", "Study"),
        ("career", "Career"),
        ("finance", "Finance"),
        ("relationship", "Relationship"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("paused", "Paused"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="goals"
    )

    title = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="other"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active"
    )

    created_by_ai = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Habit(models.Model):

    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]

    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    UNIT_CHOICES = [
        ("times", "Times"),
        ("minutes", "Minutes"),
        ("hours", "Hours"),
        ("glasses", "Glasses"),
        ("pages", "Pages"),
    ]

    goal = models.ForeignKey(
        Goal,
        on_delete=models.SET_NULL,
        related_name="habits",
        null=True,
        blank=True
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="habits"
    )

    title = models.CharField(max_length=150)

    description = models.TextField(blank=True)

    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default="daily"
    )

    daily_goal = models.PositiveIntegerField(
        default=1,
        help_text="Number of `unit`s the user aims to complete per day for this habit."
    )

    streak = models.PositiveIntegerField(default=0)

    best_streak = models.PositiveIntegerField(
        default=0,
        help_text="Longest streak ever achieved for this habit, kept in sync "
                   "with real HabitRecord history whenever records change.",
    )

    streak_goal = models.PositiveIntegerField(default=21)

    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="easy"
    )

    unit = models.CharField(
        max_length=20,
        choices=UNIT_CHOICES,
        default="times",
        help_text="Unit the habit's progress is measured in, e.g. minutes for "
                   "'meditate', glasses for 'drink water', pages for 'read'."
    )

    reminder_time = models.TimeField(
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    created_by_ai = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class HabitRecord(models.Model):

    FAILURE_REASONS = [
        ("forgot", "Forgot"),
        ("busy", "Busy"),
        ("tired", "Too Tired"),
        ("sick", "Sick"),
        ("no_motivation", "No Motivation"),
        ("other", "Other"),
    ]

    habit = models.ForeignKey(
        Habit,
        on_delete=models.CASCADE,
        related_name="records"
    )

    date = models.DateField()

    done = models.BooleanField(default=False)

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    energy = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )

    mood = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )

    failure_reason = models.CharField(
        max_length=30,
        choices=FAILURE_REASONS,
        blank=True
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("habit", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.habit.title} - {self.date}"