# Generated migration for PoliceStation model

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='PoliceStation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Unique identifier (UUID v4)', primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Timestamp when record was created')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Timestamp when record was last updated')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='Soft delete flag - records are never physically deleted')),
                ('deleted_at', models.DateTimeField(blank=True, help_text='Timestamp when record was soft-deleted', null=True)),
                ('name', models.CharField(help_text='Station name', max_length=255)),
                ('code', models.CharField(db_index=True, help_text='Unique station code (e.g., PS-MH-MUM-001)', max_length=50, unique=True)),
                ('latitude', models.DecimalField(decimal_places=6, help_text='Station latitude coordinate', max_digits=9)),
                ('longitude', models.DecimalField(decimal_places=6, help_text='Station longitude coordinate', max_digits=9)),
                ('city', models.CharField(db_index=True, help_text='City name', max_length=100)),
                ('district', models.CharField(db_index=True, help_text='District name', max_length=100)),
                ('state', models.CharField(db_index=True, help_text='State name', max_length=100)),
                ('is_active', models.BooleanField(db_index=True, default=True, help_text='Whether station is active and accepting cases')),
            ],
            options={
                'verbose_name': 'Police Station',
                'verbose_name_plural': 'Police Stations',
                'db_table': 'police_stations',
                'ordering': ['state', 'district', 'city', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='policestation',
            index=models.Index(fields=['latitude', 'longitude'], name='station_coords_idx'),
        ),
        migrations.AddIndex(
            model_name='policestation',
            index=models.Index(fields=['state', 'district', 'city'], name='station_hierarchy_idx'),
        ),
        migrations.AddIndex(
            model_name='policestation',
            index=models.Index(fields=['is_active', 'state'], name='station_active_state_idx'),
        ),
    ]
