# Generated manually (renames daily_goal -> weekly_goal)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('habits', '0004_alter_habit_daily_goal_alter_habit_streak'),
    ]

    operations = [
        migrations.RenameField(
            model_name='habit',
            old_name='daily_goal',
            new_name='weekly_goal',
        ),
        migrations.AlterField(
            model_name='habit',
            name='weekly_goal',
            field=models.PositiveIntegerField(
                default=1,
                help_text='Target number of completions per week for this habit.',
            ),
        ),
    ]
