"""
Migration for Phase 6.1: Text-only report submission.

Adds:
- text_content: Plain text report content
- latitude/longitude: Optional location coordinates
- Makes encrypted fields optional (nullable)
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0001_initial'),
    ]

    operations = [
        # Add plain text content field for Phase 6.1
        migrations.AddField(
            model_name='report',
            name='text_content',
            field=models.TextField(
                blank=True,
                help_text='Plain text report content (Phase 6.1 - pre-encryption)'
            ),
        ),
        
        # Add latitude field
        migrations.AddField(
            model_name='report',
            name='latitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='Latitude coordinate (optional)',
                max_digits=10,
                null=True
            ),
        ),
        
        # Add longitude field
        migrations.AddField(
            model_name='report',
            name='longitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='Longitude coordinate (optional)',
                max_digits=10,
                null=True
            ),
        ),
        
        # Make encrypted_title optional
        migrations.AlterField(
            model_name='report',
            name='encrypted_title',
            field=models.BinaryField(
                blank=True,
                help_text='AES-256-GCM encrypted title',
                null=True
            ),
        ),
        
        # Make encrypted_content optional
        migrations.AlterField(
            model_name='report',
            name='encrypted_content',
            field=models.BinaryField(
                blank=True,
                help_text='AES-256-GCM encrypted content',
                null=True
            ),
        ),
        
        # Make encryption_iv optional
        migrations.AlterField(
            model_name='report',
            name='encryption_iv',
            field=models.BinaryField(
                blank=True,
                help_text='Initialization vector for AES-GCM',
                max_length=16,
                null=True
            ),
        ),
        
        # Make encryption_tag optional
        migrations.AlterField(
            model_name='report',
            name='encryption_tag',
            field=models.BinaryField(
                blank=True,
                help_text='Authentication tag for AES-GCM',
                max_length=16,
                null=True
            ),
        ),
        
        # Make encryption_key_id optional
        migrations.AlterField(
            model_name='report',
            name='encryption_key_id',
            field=models.CharField(
                blank=True,
                help_text='Identifier for the encryption key (for key rotation)',
                max_length=64
            ),
        ),
        
        # Make jurisdiction_code optional (blank allowed)
        migrations.AlterField(
            model_name='report',
            name='jurisdiction_code',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Jurisdiction code for routing',
                max_length=50
            ),
        ),
    ]
