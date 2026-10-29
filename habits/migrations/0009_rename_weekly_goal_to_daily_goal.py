from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('habits', '0008_habit_unit'),
    ]

    operations = [
        migrations.RenameField(
            model_name='habit',
            old_name='weekly_goal',
            new_name='daily_goal',
        ),
        migrations.AlterField(
            model_name='habit',
            name='daily_goal',
            field=models.PositiveIntegerField(
                default=1,
                help_text="Number of `unit`s the user aims to complete per day for this habit.",
            ),
        ),
    ]
