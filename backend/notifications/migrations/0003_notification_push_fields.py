# Generated migration for Notification model updates (push fields, new types)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_rename_notificatio_recipie_7d7c8d_idx_notificatio_recipie_dde14f_idx_and_more'),
    ]

    operations = [
        # Add push notification tracking fields
        migrations.AddField(
            model_name='notification',
            name='push_sent',
            field=models.BooleanField(
                default=False,
                help_text='Whether push notification was sent'
            ),
        ),
        migrations.AddField(
            model_name='notification',
            name='push_sent_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When push notification was sent',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='notification',
            name='push_error',
            field=models.TextField(
                blank=True,
                help_text='Error message if push failed',
                null=True
            ),
        ),
        # Update notification_type choices to include new types
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('new_case', 'New Case Created'),
                    ('case_assigned', 'Case Assigned'),
                    ('case_unassigned', 'Case Unassigned'),
                    ('case_escalated', 'Case Escalated'),
                    ('case_solved', 'Case Solved'),
                    ('case_rejected', 'Case Rejected'),
                    ('case_closed', 'Case Closed'),
                    ('sla_warning', 'SLA Warning'),
                    ('sla_breached', 'SLA Breached'),
                    ('chat_message', 'New Chat Message'),
                    ('admin_action', 'Admin Action'),
                    ('general', 'General'),
                ],
                db_index=True,
                default='general',
                help_text='Type of notification',
                max_length=30
            ),
        ),
    ]
