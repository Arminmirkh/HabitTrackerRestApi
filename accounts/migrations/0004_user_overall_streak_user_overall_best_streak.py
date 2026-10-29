from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_user_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='overall_streak',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='user',
            name='overall_best_streak',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
