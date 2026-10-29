from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('habits', '0007_habit_best_streak'),
    ]

    operations = [
        migrations.AddField(
            model_name='habit',
            name='unit',
            field=models.CharField(
                choices=[
                    ('times', 'Times'),
                    ('minutes', 'Minutes'),
                    ('hours', 'Hours'),
                    ('glasses', 'Glasses'),
                    ('pages', 'Pages'),
                ],
                default='times',
                help_text="Unit the habit's progress is measured in, e.g. minutes for "
                          "'meditate', glasses for 'drink water', pages for 'read'.",
                max_length=20,
            ),
        ),
    ]
