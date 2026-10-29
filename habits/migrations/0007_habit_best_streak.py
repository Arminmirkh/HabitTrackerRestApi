from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('habits', '0006_alter_habitrecord_options_habit_created_by_ai_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='habit',
            name='best_streak',
            field=models.PositiveIntegerField(
                default=0,
                help_text="Longest streak ever achieved for this habit, kept in sync "
                          "with real HabitRecord history whenever records change.",
            ),
        ),
    ]
