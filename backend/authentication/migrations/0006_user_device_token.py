# Schema corrections migration - add device_token

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0005_user_police_station_and_roles'),
    ]

    operations = [
        # Add device_token field for push notifications
        migrations.AddField(
            model_name='user',
            name='device_token',
            field=models.CharField(
                blank=True,
                help_text='FCM/APNs token for push notifications',
                max_length=255,
                null=True
            ),
        ),
    ]
