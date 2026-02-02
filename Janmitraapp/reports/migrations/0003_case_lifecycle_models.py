"""
Migration for Case lifecycle models.

Introduces:
- Incident: Immutable citizen submission
- Case: Managed lifecycle with SLA tracking
- CaseNote: Collaborative append-only notes
- CaseStatusHistory: Immutable status timeline

This migration adds new tables without modifying existing ones.
Backward compatible with existing Report models.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0002_phase61_text_only_reports'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create Incident table
        migrations.CreateModel(
            name='Incident',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4,
                    editable=False,
                    help_text='Unique identifier (UUID v4)',
                    primary_key=True,
                    serialize=False
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    help_text='Timestamp when record was created'
                )),
                ('updated_at', models.DateTimeField(
                    auto_now=True,
                    help_text='Timestamp when record was last updated'
                )),
                ('is_deleted', models.BooleanField(
                    db_index=True,
                    default=False,
                    help_text='Soft delete flag - records are never physically deleted'
                )),
                ('deleted_at', models.DateTimeField(
                    blank=True,
                    help_text='Timestamp when record was soft-deleted',
                    null=True
                )),
                ('text_content', models.TextField(
                    help_text='Incident description text (required)'
                )),
                ('category', models.CharField(
                    choices=[
                        ('general', 'General'),
                        ('public_safety', 'Public Safety'),
                        ('infrastructure', 'Infrastructure'),
                        ('environmental', 'Environmental'),
                        ('social', 'Social'),
                        ('economic', 'Economic'),
                        ('governance', 'Governance'),
                        ('other', 'Other'),
                    ],
                    db_index=True,
                    default='general',
                    help_text='Incident category',
                    max_length=30
                )),
                ('latitude', models.DecimalField(
                    blank=True,
                    decimal_places=7,
                    help_text='Latitude coordinate (optional)',
                    max_digits=10,
                    null=True
                )),
                ('longitude', models.DecimalField(
                    blank=True,
                    decimal_places=7,
                    help_text='Longitude coordinate (optional)',
                    max_digits=10,
                    null=True
                )),
                ('submitted_by', models.ForeignKey(
                    help_text='JanMitra member who submitted this incident',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='incidents',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'incidents',
                'ordering': ['-created_at'],
                'verbose_name': 'Incident',
                'verbose_name_plural': 'Incidents',
            },
        ),
        
        # Create Case table
        migrations.CreateModel(
            name='Case',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4,
                    editable=False,
                    help_text='Unique identifier (UUID v4)',
                    primary_key=True,
                    serialize=False
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    help_text='Timestamp when record was created'
                )),
                ('updated_at', models.DateTimeField(
                    auto_now=True,
                    help_text='Timestamp when record was last updated'
                )),
                ('is_deleted', models.BooleanField(
                    db_index=True,
                    default=False,
                    help_text='Soft delete flag - records are never physically deleted'
                )),
                ('deleted_at', models.DateTimeField(
                    blank=True,
                    help_text='Timestamp when record was soft-deleted',
                    null=True
                )),
                ('current_level', models.IntegerField(
                    choices=[
                        (2, 'Level 2 - Field Officers'),
                        (1, 'Level 1 - Senior Officers'),
                        (0, 'Level 0 - Highest Authority'),
                    ],
                    db_index=True,
                    default=2,
                    help_text='Current handling level (2=Field, 1=Senior, 0=Highest)'
                )),
                ('status', models.CharField(
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
                )),
                ('sla_deadline', models.DateTimeField(
                    db_index=True,
                    help_text='Deadline for current level to resolve before auto-escalation'
                )),
                ('solved_at', models.DateTimeField(
                    blank=True,
                    help_text='When the case was solved',
                    null=True
                )),
                ('solution_notes', models.TextField(
                    blank=True,
                    help_text='Notes about the solution'
                )),
                ('rejected_at', models.DateTimeField(
                    blank=True,
                    help_text='When the case was rejected',
                    null=True
                )),
                ('rejection_reason', models.TextField(
                    blank=True,
                    help_text='Reason for rejection'
                )),
                ('escalation_count', models.PositiveSmallIntegerField(
                    default=0,
                    help_text='Number of times this case has been escalated'
                )),
                ('last_escalated_at', models.DateTimeField(
                    blank=True,
                    help_text='When the case was last escalated',
                    null=True
                )),
                ('incident', models.OneToOneField(
                    help_text='Source incident for this case',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='case',
                    to='reports.incident'
                )),
                ('solved_by', models.ForeignKey(
                    blank=True,
                    help_text='Officer who solved this case (locks case)',
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='cases_solved',
                    to=settings.AUTH_USER_MODEL
                )),
                ('rejected_by', models.ForeignKey(
                    blank=True,
                    help_text='Officer who rejected this case',
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='cases_rejected',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'cases',
                'ordering': ['-created_at'],
                'verbose_name': 'Case',
                'verbose_name_plural': 'Cases',
            },
        ),
        
        # Add indexes for Case
        migrations.AddIndex(
            model_name='case',
            index=models.Index(
                fields=['status', 'current_level'],
                name='cases_status_level_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='case',
            index=models.Index(
                fields=['sla_deadline'],
                name='cases_sla_deadline_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='case',
            index=models.Index(
                fields=['current_level', 'status', 'sla_deadline'],
                name='cases_level_status_sla_idx'
            ),
        ),
        
        # Create CaseNote table
        migrations.CreateModel(
            name='CaseNote',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4,
                    editable=False,
                    help_text='Unique identifier (UUID v4)',
                    primary_key=True,
                    serialize=False
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    help_text='Timestamp when record was created'
                )),
                ('updated_at', models.DateTimeField(
                    auto_now=True,
                    help_text='Timestamp when record was last updated'
                )),
                ('is_deleted', models.BooleanField(
                    db_index=True,
                    default=False,
                    help_text='Soft delete flag - records are never physically deleted'
                )),
                ('deleted_at', models.DateTimeField(
                    blank=True,
                    help_text='Timestamp when record was soft-deleted',
                    null=True
                )),
                ('author_level', models.CharField(
                    choices=[
                        ('LEVEL_2', 'Level 2'),
                        ('LEVEL_1', 'Level 1'),
                        ('LEVEL_0', 'Level 0'),
                    ],
                    help_text="Author's role level at time of note creation",
                    max_length=10
                )),
                ('note_text', models.TextField(
                    help_text='Note content'
                )),
                ('case', models.ForeignKey(
                    help_text='Case this note belongs to',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='notes',
                    to='reports.case'
                )),
                ('author', models.ForeignKey(
                    help_text='Officer who wrote this note',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='case_notes',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'case_notes',
                'ordering': ['-created_at'],
                'verbose_name': 'Case Note',
                'verbose_name_plural': 'Case Notes',
            },
        ),
        
        # Create CaseStatusHistory table
        migrations.CreateModel(
            name='CaseStatusHistory',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4,
                    editable=False,
                    help_text='Unique identifier (UUID v4)',
                    primary_key=True,
                    serialize=False
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    help_text='Timestamp when record was created'
                )),
                ('updated_at', models.DateTimeField(
                    auto_now=True,
                    help_text='Timestamp when record was last updated'
                )),
                ('is_deleted', models.BooleanField(
                    db_index=True,
                    default=False,
                    help_text='Soft delete flag - records are never physically deleted'
                )),
                ('deleted_at', models.DateTimeField(
                    blank=True,
                    help_text='Timestamp when record was soft-deleted',
                    null=True
                )),
                ('from_status', models.CharField(
                    choices=[
                        ('open', 'Open'),
                        ('solved', 'Solved'),
                        ('rejected', 'Rejected'),
                        ('closed', 'Closed'),
                    ],
                    help_text='Previous status',
                    max_length=20
                )),
                ('to_status', models.CharField(
                    choices=[
                        ('open', 'Open'),
                        ('solved', 'Solved'),
                        ('rejected', 'Rejected'),
                        ('closed', 'Closed'),
                    ],
                    help_text='New status',
                    max_length=20
                )),
                ('from_level', models.IntegerField(
                    blank=True,
                    choices=[
                        (2, 'Level 2 - Field Officers'),
                        (1, 'Level 1 - Senior Officers'),
                        (0, 'Level 0 - Highest Authority'),
                    ],
                    help_text='Previous handling level (for escalation tracking)',
                    null=True
                )),
                ('to_level', models.IntegerField(
                    blank=True,
                    choices=[
                        (2, 'Level 2 - Field Officers'),
                        (1, 'Level 1 - Senior Officers'),
                        (0, 'Level 0 - Highest Authority'),
                    ],
                    help_text='New handling level (for escalation tracking)',
                    null=True
                )),
                ('reason', models.TextField(
                    blank=True,
                    help_text='Reason for status change'
                )),
                ('is_auto_escalation', models.BooleanField(
                    default=False,
                    help_text='True if this was an automatic SLA-based escalation'
                )),
                ('case', models.ForeignKey(
                    help_text='Case this history entry belongs to',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='status_history',
                    to='reports.case'
                )),
                ('changed_by', models.ForeignKey(
                    blank=True,
                    help_text='User who changed status (null for system/auto-escalation)',
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='case_status_changes',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'case_status_history',
                'ordering': ['-created_at'],
                'verbose_name': 'Case Status History',
                'verbose_name_plural': 'Case Status Histories',
            },
        ),
    ]
