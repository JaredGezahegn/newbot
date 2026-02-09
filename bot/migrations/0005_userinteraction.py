# Generated manually for UserInteraction model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0004_feedback'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserInteraction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('interaction_type', models.CharField(max_length=50)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='interactions', to='bot.user')),
            ],
        ),
        migrations.AddIndex(
            model_name='userinteraction',
            index=models.Index(fields=['user', 'timestamp'], name='bot_userinteraction_user_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='userinteraction',
            index=models.Index(fields=['timestamp'], name='bot_userinteraction_timestamp_idx'),
        ),
    ]
