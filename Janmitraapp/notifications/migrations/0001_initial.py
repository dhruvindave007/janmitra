# Generated manually for Phase 4.2: Notification System

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reports', '0004_incident_broadcast_api'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False, help_text='Soft delete flag')),
                ('title', models.CharField(help_text='Short notification title', max_length=200)),
                ('message', models.TextField(help_text='Notification message body')),
                ('notification_type', models.CharField(
                    choices=[
                        ('new_case', 'New Case Assigned'),
                        ('case_escalated', 'Case Escalated'),
                        ('case_solved', 'Case Solved'),
                        ('case_rejected', 'Case Rejected'),
                        ('case_closed', 'Case Closed'),
                        ('sla_warning', 'SLA Warning'),
                        ('sla_breached', 'SLA Breached'),
                        ('admin_action', 'Admin Action'),
                        ('general', 'General'),
                    ],
                    db_index=True,
                    default='general',
                    help_text='Type of notification',
                    max_length=30,
                )),
                ('level', models.IntegerField(blank=True, help_text='Authority level this notification is for', null=True)),
                ('is_read', models.BooleanField(db_index=True, default=False, help_text='Whether the notification has been read')),
                ('read_at', models.DateTimeField(blank=True, help_text='When the notification was read', null=True)),
                ('case', models.ForeignKey(
                    blank=True,
                    help_text='Related case (if applicable)',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='notifications',
                    to='reports.case',
                )),
                ('recipient', models.ForeignKey(
                    help_text='User who receives this notification',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Notification',
                'verbose_name_plural': 'Notifications',
                'db_table': 'notifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient', 'is_read', '-created_at'], name='notificatio_recipie_7d7c8d_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient', '-created_at'], name='notificatio_recipie_b3e9e0_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['notification_type', '-created_at'], name='notificatio_notific_e5c2ab_idx'),
        ),
    ]
