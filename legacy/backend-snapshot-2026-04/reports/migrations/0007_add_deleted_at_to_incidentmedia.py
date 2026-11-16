from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0006_incident_media'),
    ]

    operations = [
        migrations.AddField(
            model_name='incidentmedia',
            name='deleted_at',
            field=models.DateTimeField(null=True, blank=True, help_text='Timestamp when record was soft-deleted'),
        ),
    ]
