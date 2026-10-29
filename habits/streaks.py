"""
Streak calculation.

Computed fresh from HabitRecord history every time -- never trusts a
running counter, since a counter can drift (backfilling a past date,
deleting a record, etc. would silently desync a naive increment/reset
field).

- "daily" habits: a streak is a run of consecutive calendar days with
  a done record.
- "weekly"/"monthly" habits: a streak is a run of consecutive weeks
  (ISO week) or months in which the habit was done on at least one
  day of that period (there is no per-period completion count target
  anymore now that weekly_goal has been replaced by daily_goal, which
  measures a per-day quantity, not a per-period attempt count).

Also provides calculate_overall_streak()/resync_overall_streak(), a
cross-habit version: consecutive days on which the user completed at
least one of their habits (any habit), used for a user-level
"overall streak" independent of any single habit's frequency.

Today's (or the current period's) entry is allowed to be missing
without breaking the current streak, since it isn't over yet -- but
it IS required for the *longest* streak once it's actually met.
"""
from collections import defaultdict
from datetime import date, timedelta

from django.utils import timezone


def _longest_consecutive_days(done_dates):
    if not done_dates:
        return 0
    sorted_dates = sorted(done_dates)
    longest = run = 1
    for prev, curr in zip(sorted_dates, sorted_dates[1:]):
        gap = (curr - prev).days
        if gap == 1:
            run += 1
            longest = max(longest, run)
        elif gap > 1:
            run = 1
    return longest


def _daily_streak(done_dates):
    today = timezone.localdate()
    longest = _longest_consecutive_days(done_dates)

    cursor = today if today in done_dates else today - timedelta(days=1)
    current = 0
    while cursor in done_dates:
        current += 1
        cursor -= timedelta(days=1)

    return {
        "current_streak": current,
        "longest_streak": longest,
        "unit": "days",
    }


def _period_key(d, period):
    if period == "week":
        iso_year, iso_week, _ = d.isocalendar()
        return (iso_year, iso_week)
    return (d.year, d.month)


def _shift_period(key, period, delta_weeks_or_months):
    if period == "week":
        year, week = key
        anchor = date.fromisocalendar(year, week, 1) + timedelta(weeks=delta_weeks_or_months)
        iso_year, iso_week, _ = anchor.isocalendar()
        return (iso_year, iso_week)

    year, month = key
    month0 = (year * 12 + (month - 1)) + delta_weeks_or_months
    return (month0 // 12, month0 % 12 + 1)


def _periodic_streak(done_dates, period):
    counts = defaultdict(int)
    for d in done_dates:
        counts[_period_key(d, period)] += 1

    # A period counts as "met" if the habit was done at least once in
    # it -- weekly_goal (a per-period completion count) was removed in
    # favor of daily_goal (a per-day quantity), so there is no longer a
    # meaningful per-period target to compare against.
    met_periods = {key for key, count in counts.items() if count >= 1}
    unit = "weeks" if period == "week" else "months"

    if not met_periods:
        return {"current_streak": 0, "longest_streak": 0, "unit": unit}

    sorted_keys = sorted(met_periods)
    longest = run = 1
    for prev_key, curr_key in zip(sorted_keys, sorted_keys[1:]):
        if _shift_period(prev_key, period, 1) == curr_key:
            run += 1
            longest = max(longest, run)
        else:
            run = 1

    current_key = _period_key(timezone.localdate(), period)
    cursor = current_key if current_key in met_periods else _shift_period(current_key, period, -1)
    current = 0
    while cursor in met_periods:
        current += 1
        cursor = _shift_period(cursor, period, -1)

    return {"current_streak": current, "longest_streak": longest, "unit": unit}


def calculate_streak(habit):
    """
    Returns {"current_streak": int, "longest_streak": int, "unit": str}
    computed from habit.records (a HabitRecord related_name), using
    the rule appropriate to habit.frequency.
    """
    done_dates = set(habit.records.filter(done=True).values_list("date", flat=True))

    if not done_dates:
        unit = "days" if habit.frequency == "daily" else (
            "weeks" if habit.frequency == "weekly" else "months"
        )
        return {"current_streak": 0, "longest_streak": 0, "unit": unit}

    if habit.frequency == "weekly":
        return _periodic_streak(done_dates, "week")
    if habit.frequency == "monthly":
        return _periodic_streak(done_dates, "month")
    return _daily_streak(done_dates)


def calculate_overall_streak(user):
    """
    Cross-habit streak: consecutive days on which the user completed
    at least one habit, regardless of which one. Uses the same
    day-based rule as daily-frequency habits.
    """
    from .models import HabitRecord

    done_dates = set(
        HabitRecord.objects.filter(habit__user=user, done=True).values_list("date", flat=True)
    )
    return _daily_streak(done_dates)


def resync_overall_streak(user):
    """
    Recomputes and persists user.overall_streak / overall_best_streak
    if they've drifted from the real calculation. Call this whenever a
    HabitRecord changes (create/update/delete), same as per-habit
    streaks. Safe to call even if nothing changed (no-op write).
    """
    result = calculate_overall_streak(user)
    update_fields = []
    if user.overall_streak != result["current_streak"]:
        user.overall_streak = result["current_streak"]
        update_fields.append("overall_streak")
    if user.overall_best_streak != result["longest_streak"]:
        user.overall_best_streak = result["longest_streak"]
        update_fields.append("overall_best_streak")
    if update_fields:
        user.save(update_fields=update_fields)
