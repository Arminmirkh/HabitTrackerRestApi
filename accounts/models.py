from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    # Overridden to be required + unique so it can be used as the
    # login identifier (see accounts.serializers.LoginSerializer).
    email = models.EmailField(unique=True)
    age = models.PositiveSmallIntegerField(null=True,blank=True)
    gender = models.CharField(
        max_length=1,
        choices=[('M', 'Male'), ('F', 'Female')],
        null=True,
        blank=True
    )

    # Cross-habit streak: consecutive days on which the user completed
    # at least one habit (any habit), not tied to a single habit's own
    # frequency. Kept in sync from habits.streaks.resync_overall_streak
    # whenever a HabitRecord changes, and recomputed fresh on every read
    # of the profile (see accounts.serializers.ProfileSerializer) so it
    # never goes stale just because the user hasn't checked in today.
    overall_streak = models.PositiveIntegerField(default=0)
    overall_best_streak = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.username
