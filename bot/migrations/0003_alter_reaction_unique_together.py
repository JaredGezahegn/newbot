# Generated migration to change Reaction unique_together constraint

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0002_comment_confession_reaction_alter_user_options_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='reaction',
            unique_together={('comment', 'user', 'reaction_type')},
        ),
    ]
