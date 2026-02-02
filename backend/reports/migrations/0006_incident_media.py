# Generated for Phase 6.3.2: Incident Media Storage

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import reports.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reports', '0005_add_incident_area_metadata'),
    ]

    operations = [
        migrations.CreateModel(
            name='IncidentMedia',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False, help_text='Soft delete flag')),
                ('file', models.FileField(
                    help_text='Uploaded media file',
                    upload_to=reports.models.incident_media_path,
                )),
                ('media_type', models.CharField(
                    choices=[('photo', 'Photo'), ('video', 'Video')],
                    db_index=True,
                    help_text='Type of media (photo/video)',
                    max_length=10,
                )),
                ('original_filename', models.CharField(
                    blank=True,
                    help_text='Original filename (for reference only)',
                    max_length=255,
                )),
                ('file_size', models.PositiveIntegerField(
                    default=0,
                    help_text='File size in bytes',
                )),
                ('content_type', models.CharField(
                    blank=True,
                    help_text='MIME type of the file',
                    max_length=100,
                )),
                ('incident', models.ForeignKey(
                    help_text='Incident this media belongs to',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='media_files',
                    to='reports.incident',
                )),
                ('uploaded_by', models.ForeignKey(
                    help_text='User who uploaded this media',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='uploaded_incident_media',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Incident Media',
                'verbose_name_plural': 'Incident Media',
                'db_table': 'incident_media',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='incidentmedia',
            index=models.Index(fields=['incident', 'created_at'], name='incident_me_inciden_7f3c8a_idx'),
        ),
    ]
