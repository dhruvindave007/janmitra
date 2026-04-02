# Generated migration for Case model updates and new models

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import reports.models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0008_rename_incident_me_inciden_7f3c8a_idx_incident_me_inciden_1e87ca_idx_and_more'),
        ('authentication', '0005_user_police_station_and_roles'),
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # =====================================================================
        # Case model updates
        # =====================================================================
        
        # Add police_station FK to Case
        migrations.AddField(
            model_name='case',
            name='police_station',
            field=models.ForeignKey(
                blank=True,
                help_text='Police station this case is routed to',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cases',
                to='core.policestation'
            ),
        ),
        
        # Change current_level from IntegerField to CharField
        migrations.AlterField(
            model_name='case',
            name='current_level',
            field=models.CharField(
                db_index=True,
                default='L2',
                help_text='Current handling level (L0/L1/L2/L3/L4)',
                max_length=10
            ),
        ),
        
        # Add assigned_officer FK
        migrations.AddField(
            model_name='case',
            name='assigned_officer',
            field=models.ForeignKey(
                blank=True,
                help_text='L0 officer assigned to this case',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='assigned_cases',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        
        # Add assigned_by FK
        migrations.AddField(
            model_name='case',
            name='assigned_by',
            field=models.ForeignKey(
                blank=True,
                help_text='L1 who assigned the officer',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='case_assignments_made',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        
        # Add assigned_at
        migrations.AddField(
            model_name='case',
            name='assigned_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When officer was assigned',
                null=True
            ),
        ),
        
        # Add is_sla_breached
        migrations.AddField(
            model_name='case',
            name='is_sla_breached',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='Whether SLA has been breached'
            ),
        ),
        
        # Add closed_at
        migrations.AddField(
            model_name='case',
            name='closed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        
        # Add closed_by FK
        migrations.AddField(
            model_name='case',
            name='closed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cases_closed',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        
        # Add closed_by_level
        migrations.AddField(
            model_name='case',
            name='closed_by_level',
            field=models.CharField(
                blank=True,
                help_text='Level of the user who closed the case',
                max_length=10,
                null=True
            ),
        ),
        
        # Add is_chat_locked
        migrations.AddField(
            model_name='case',
            name='is_chat_locked',
            field=models.BooleanField(
                default=False,
                help_text='Whether investigation chat is locked (after case closure)'
            ),
        ),
        
        # Add new indexes for Case
        migrations.AddIndex(
            model_name='case',
            index=models.Index(fields=['police_station', 'status'], name='case_station_status_idx'),
        ),
        migrations.AddIndex(
            model_name='case',
            index=models.Index(fields=['police_station', 'current_level', 'status'], name='case_station_level_idx'),
        ),
        migrations.AddIndex(
            model_name='case',
            index=models.Index(fields=['assigned_officer', 'status'], name='case_officer_status_idx'),
        ),
        migrations.AddIndex(
            model_name='case',
            index=models.Index(fields=['is_sla_breached'], name='case_sla_breach_idx'),
        ),
        
        # =====================================================================
        # InvestigationMessage model (new)
        # =====================================================================
        
        migrations.CreateModel(
            name='InvestigationMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Unique identifier (UUID v4)', primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Timestamp when record was created')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Timestamp when record was last updated')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='Soft delete flag - records are never physically deleted')),
                ('deleted_at', models.DateTimeField(blank=True, help_text='Timestamp when record was soft-deleted', null=True)),
                ('sender_role', models.CharField(db_index=True, help_text="Sender's role at time of sending (L0/L1/L2/L3/L4/SYSTEM)", max_length=20)),
                ('message_type', models.CharField(choices=[('text', 'Text Message'), ('media', 'Media Message'), ('system', 'System Message')], db_index=True, default='text', help_text='Type of message', max_length=10)),
                ('text_content', models.TextField(blank=True, help_text='Message text content', null=True)),
                ('file', models.FileField(blank=True, help_text='Attached media file', null=True, upload_to=reports.models.investigation_media_path)),
                ('file_name', models.CharField(blank=True, help_text='Original filename', max_length=255, null=True)),
                ('file_size', models.BigIntegerField(blank=True, help_text='File size in bytes', null=True)),
                ('file_type', models.CharField(blank=True, help_text='MIME type of the file', max_length=100, null=True)),
                ('case', models.ForeignKey(help_text='Case this message belongs to', on_delete=django.db.models.deletion.PROTECT, related_name='investigation_messages', to='reports.case')),
                ('sender', models.ForeignKey(blank=True, help_text='User who sent this message (null for system)', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='investigation_messages_sent', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Investigation Message',
                'verbose_name_plural': 'Investigation Messages',
                'db_table': 'investigation_messages',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='investigationmessage',
            index=models.Index(fields=['case', 'created_at'], name='inv_msg_case_time_idx'),
        ),
        migrations.AddIndex(
            model_name='investigationmessage',
            index=models.Index(fields=['sender'], name='inv_msg_sender_idx'),
        ),
        
        # =====================================================================
        # EscalationHistory model (new)
        # =====================================================================
        
        migrations.CreateModel(
            name='EscalationHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Unique identifier (UUID v4)', primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Timestamp when record was created')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Timestamp when record was last updated')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='Soft delete flag - records are never physically deleted')),
                ('deleted_at', models.DateTimeField(blank=True, help_text='Timestamp when record was soft-deleted', null=True)),
                ('from_level', models.CharField(help_text='Level before escalation (L0/L1/L2/L3)', max_length=10)),
                ('to_level', models.CharField(help_text='Level after escalation (L3/L4)', max_length=10)),
                ('escalation_type', models.CharField(choices=[('auto', 'Automatic (SLA Breach)'), ('manual', 'Manual Escalation')], db_index=True, help_text='Type of escalation', max_length=10)),
                ('reason', models.TextField(help_text='Reason for escalation')),
                ('case', models.ForeignKey(help_text='Case that was escalated', on_delete=django.db.models.deletion.PROTECT, related_name='escalation_history', to='reports.case')),
                ('escalated_by', models.ForeignKey(blank=True, help_text='User who initiated escalation (null for auto)', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='escalations_initiated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Escalation History',
                'verbose_name_plural': 'Escalation Histories',
                'db_table': 'escalation_history',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='escalationhistory',
            index=models.Index(fields=['case', 'created_at'], name='esc_hist_case_time_idx'),
        ),
        migrations.AddIndex(
            model_name='escalationhistory',
            index=models.Index(fields=['escalation_type'], name='esc_hist_type_idx'),
        ),
    ]
