# Schema corrections migration

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0009_case_updates_and_new_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # =====================================================================
        # Case model schema corrections
        # =====================================================================
        
        # Update current_level to include choices
        migrations.AlterField(
            model_name='case',
            name='current_level',
            field=models.CharField(
                choices=[
                    ('L0', 'L0 - Field Officer'),
                    ('L1', 'L1 - PSO'),
                    ('L2', 'L2 - PI'),
                    ('L3', 'L3 - Higher Authority'),
                    ('L4', 'L4 - Top Authority'),
                ],
                db_index=True,
                default='L2',
                help_text='Current handling level (L0/L1/L2/L3/L4)',
                max_length=10
            ),
        ),
        
        # Update status to include explicit choices
        migrations.AlterField(
            model_name='case',
            name='status',
            field=models.CharField(
                choices=[
                    ('open', 'Open'),
                    ('solved', 'Solved'),
                    ('rejected', 'Rejected'),
                    ('closed', 'Closed'),
                ],
                db_index=True,
                default='open',
                help_text='Current case status',
                max_length=20
            ),
        ),
        
        # Remove is_sla_breached
        migrations.RemoveIndex(
            model_name='case',
            name='case_sla_breach_idx',
        ),
        migrations.RemoveField(
            model_name='case',
            name='is_sla_breached',
        ),
        
        # Add sla_breached_at
        migrations.AddField(
            model_name='case',
            name='sla_breached_at',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text='When SLA was breached (null if not breached)',
                null=True
            ),
        ),
        
        # Add new index for sla_breached_at
        migrations.AddIndex(
            model_name='case',
            index=models.Index(fields=['sla_breached_at'], name='case_sla_breach_idx'),
        ),
        
        # =====================================================================
        # EscalationHistory schema corrections
        # =====================================================================
        
        # Add event_type field
        migrations.AddField(
            model_name='escalationhistory',
            name='event_type',
            field=models.CharField(
                choices=[('escalation', 'Escalation'), ('assignment', 'Assignment')],
                db_index=True,
                default='escalation',
                help_text='Type of event (escalation or assignment)',
                max_length=15
            ),
        ),
        
        # Update from_level to be nullable (for assignment events)
        migrations.AlterField(
            model_name='escalationhistory',
            name='from_level',
            field=models.CharField(
                blank=True,
                help_text='Level before escalation (L0/L1/L2/L3)',
                max_length=10,
                null=True
            ),
        ),
        
        # Update to_level to be nullable (for assignment events)
        migrations.AlterField(
            model_name='escalationhistory',
            name='to_level',
            field=models.CharField(
                blank=True,
                help_text='Level after escalation (L3/L4)',
                max_length=10,
                null=True
            ),
        ),
        
        # Update escalation_type to be nullable (for assignment events)
        migrations.AlterField(
            model_name='escalationhistory',
            name='escalation_type',
            field=models.CharField(
                blank=True,
                choices=[('auto', 'Automatic (SLA Breach)'), ('manual', 'Manual Escalation')],
                db_index=True,
                help_text='Type of escalation (only for escalation events)',
                max_length=10,
                null=True
            ),
        ),
        
        # Add assigned_officer FK for assignment events
        migrations.AddField(
            model_name='escalationhistory',
            name='assigned_officer',
            field=models.ForeignKey(
                blank=True,
                help_text='Officer assigned (for assignment events)',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='assignment_history',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        
        # Update reason to be nullable
        migrations.AlterField(
            model_name='escalationhistory',
            name='reason',
            field=models.TextField(
                blank=True,
                help_text='Reason for escalation or assignment notes'
            ),
        ),
        
        # Add index for event_type
        migrations.AddIndex(
            model_name='escalationhistory',
            index=models.Index(fields=['event_type'], name='esc_hist_event_type_idx'),
        ),
        
        # =====================================================================
        # InvestigationMessage schema corrections
        # =====================================================================
        
        # Add index on created_at for better timeline queries
        migrations.AddIndex(
            model_name='investigationmessage',
            index=models.Index(fields=['created_at'], name='inv_msg_created_idx'),
        ),
    ]
