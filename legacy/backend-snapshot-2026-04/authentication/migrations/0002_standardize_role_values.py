"""
Data migration to standardize role values to uppercase.

Migrates:
- 'level_1' -> 'LEVEL_1'
- 'level_2' -> 'LEVEL_2'
- 'level_3' -> 'JANMITRA'

This ensures all existing records use the new standardized role values
that match the API output expected by the Flutter client.
"""

from django.db import migrations


def standardize_roles(apps, schema_editor):
    """Convert legacy lowercase role values to new standardized values."""
    User = apps.get_model('authentication', 'User')
    
    # Map old values to new values
    role_mapping = {
        'level_1': 'LEVEL_1',
        'level_2': 'LEVEL_2',
        'level_3': 'JANMITRA',
    }
    
    for old_value, new_value in role_mapping.items():
        User.objects.filter(role=old_value).update(role=new_value)


def reverse_roles(apps, schema_editor):
    """Revert to legacy lowercase role values (for rollback)."""
    User = apps.get_model('authentication', 'User')
    
    # Map new values back to old values
    role_mapping = {
        'LEVEL_1': 'level_1',
        'LEVEL_2': 'level_2',
        'JANMITRA': 'level_3',
    }
    
    for new_value, old_value in role_mapping.items():
        User.objects.filter(role=new_value).update(role=old_value)


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(standardize_roles, reverse_roles),
    ]
