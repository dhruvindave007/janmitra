# Generated migration for User model updates (police_station FK, new roles)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0004_alter_user_role'),
        ('core', '0001_initial'),
    ]

    operations = [
        # Add police_station FK to User
        migrations.AddField(
            model_name='user',
            name='police_station',
            field=models.ForeignKey(
                blank=True,
                help_text='Assigned police station (for L0/L1/L2 officers)',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='officers',
                to='core.policestation'
            ),
        ),
        # Update role choices to include new workflow roles
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('L0', 'L0 - Field Officer'),
                    ('L1', 'L1 - PSO'),
                    ('L2', 'L2 - PI'),
                    ('L3', 'L3 - Higher Authority'),
                    ('L4', 'L4 - Top Authority'),
                    ('JANMITRA', 'Citizen'),
                    ('level_0', 'Level 0 - Super Admin (Legacy)'),
                    ('level_1', 'Level 1 - Senior Authority (Legacy)'),
                    ('level_2', 'Level 2 - Field Authority (Legacy)'),
                    ('level_2_captain', 'Level 2 Captain - Field Supervisor (Legacy)'),
                    ('level_3', 'Level 3 - JanMitra Member (Legacy)'),
                ],
                db_index=True,
                default='JANMITRA',
                help_text='User role determining access level',
                max_length=20
            ),
        ),
        # Add index for station + role lookups
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['police_station', 'role'], name='user_station_role_idx'),
        ),
    ]
