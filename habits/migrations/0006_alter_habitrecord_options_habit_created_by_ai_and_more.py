import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('habits', '0005_rename_daily_goal_to_weekly_goal'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Goal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('category', models.CharField(choices=[('fitness', 'Fitness'), ('health', 'Health'), ('study', 'Study'), ('career', 'Career'), ('finance', 'Finance'), ('relationship', 'Relationship'), ('other', 'Other')], default='other', max_length=30)),
                ('status', models.CharField(choices=[('active', 'Active'), ('completed', 'Completed'), ('paused', 'Paused')], default='active', max_length=20)),
                ('created_by_ai', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='goals', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='habit',
            name='created_by_ai',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='habit',
            name='difficulty',
            field=models.CharField(choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')], default='easy', max_length=20),
        ),
        migrations.AddField(
            model_name='habit',
            name='frequency',
            field=models.CharField(choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], default='daily', max_length=20),
        ),
        migrations.AddField(
            model_name='habit',
            name='reminder_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='habit',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='habit',
            name='goal',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='habits', to='habits.goal'),
        ),
        migrations.AlterField(
            model_name='habit',
            name='title',
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name='habit',
            name='streak',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='habit',
            name='streak_goal',
            field=models.PositiveIntegerField(default=21),
        ),
        migrations.AddField(
            model_name='habitrecord',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='habitrecord',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='habitrecord',
            name='energy',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='habitrecord',
            name='mood',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='habitrecord',
            name='failure_reason',
            field=models.CharField(blank=True, choices=[('forgot', 'Forgot'), ('busy', 'Busy'), ('tired', 'Too Tired'), ('sick', 'Sick'), ('no_motivation', 'No Motivation'), ('other', 'Other')], default='', max_length=30),
        ),
        migrations.AddField(
            model_name='habitrecord',
            name='note',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterUniqueTogether(
            name='habitrecord',
            unique_together={('habit', 'date')},
        ),
        migrations.AlterModelOptions(
            name='habitrecord',
            options={'ordering': ['-date']},
        ),
    ]
