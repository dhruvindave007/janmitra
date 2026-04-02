# Schema corrections migration - add push_attempts

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_notification_push_fields'),
    ]

    operations = [
        # Add push_attempts field
        migrations.AddField(
            model_name='notification',
            name='push_attempts',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text='Number of push notification attempts'
            ),
        ),
    ]
