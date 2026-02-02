"""
Media storage models for JanMitra Backend.

Contains:
- ReportMedia: Encrypted media files attached to reports
- MediaAccessLog: Access tracking for media files

Security features:
- All media is encrypted client-side before upload
- Backend stores only encrypted blobs
- File type validation (whitelist approach)
- Size limits enforced
- Complete access audit trail
"""

import uuid
import os
from django.db import models
from django.utils import timezone
from django.conf import settings

from core.models import BaseModel


class MediaType:
    """Allowed media types (whitelist)."""
    IMAGE = 'image'
    VIDEO = 'video'
    AUDIO = 'audio'
    DOCUMENT = 'document'
    
    CHOICES = [
        (IMAGE, 'Image'),
        (VIDEO, 'Video'),
        (AUDIO, 'Audio'),
        (DOCUMENT, 'Document'),
    ]
    
    # Allowed MIME types per category
    ALLOWED_MIME_TYPES = {
        IMAGE: [
            'image/jpeg',
            'image/png',
            'image/webp',
            'image/heic',
            'image/heif',
        ],
        VIDEO: [
            'video/mp4',
            'video/quicktime',
            'video/x-msvideo',
            'video/webm',
        ],
        AUDIO: [
            'audio/mpeg',
            'audio/mp4',
            'audio/wav',
            'audio/ogg',
            'audio/aac',
        ],
        DOCUMENT: [
            'application/pdf',
        ],
    }
    
    # Maximum file sizes in bytes
    MAX_SIZES = {
        IMAGE: 10 * 1024 * 1024,      # 10 MB
        VIDEO: 100 * 1024 * 1024,     # 100 MB
        AUDIO: 25 * 1024 * 1024,      # 25 MB
        DOCUMENT: 20 * 1024 * 1024,   # 20 MB
    }


def encrypted_media_path(instance, filename):
    """
    Generate storage path for encrypted media.
    
    Path format: encrypted_media/YYYY/MM/DD/<uuid>.<ext>
    
    The original filename is NOT used - only UUID to prevent
    any information leakage through filenames.
    """
    date = timezone.now()
    ext = os.path.splitext(filename)[1].lower() or '.bin'
    new_filename = f"{instance.id}{ext}.enc"
    return os.path.join(
        'encrypted_media',
        str(date.year),
        str(date.month).zfill(2),
        str(date.day).zfill(2),
        new_filename
    )


class ReportMedia(BaseModel):
    """
    Encrypted media file attached to a report.
    
    Security design:
    - Media is encrypted client-side using AES-256-GCM
    - Only encrypted blob is uploaded and stored
    - Original filename stored encrypted (optional)
    - Thumbnails are also encrypted
    - Decryption requires appropriate authorization
    """
    
    # Link to report
    report = models.ForeignKey(
        'reports.Report',
        on_delete=models.CASCADE,
        related_name='media_files',
        help_text="Report this media belongs to"
    )
    
    # Uploader
    uploaded_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='uploaded_media',
        help_text="User who uploaded this media"
    )
    
    # =========================================================================
    # ENCRYPTED CONTENT
    # =========================================================================
    
    # The encrypted media file
    encrypted_file = models.FileField(
        upload_to=encrypted_media_path,
        help_text="Encrypted media file"
    )
    
    # Encrypted thumbnail (for images/videos)
    encrypted_thumbnail = models.FileField(
        upload_to='encrypted_media/thumbnails/',
        null=True,
        blank=True,
        help_text="Encrypted thumbnail"
    )
    
    # Original filename (encrypted)
    encrypted_filename = models.BinaryField(
        null=True,
        blank=True,
        help_text="Encrypted original filename"
    )
    
    # Encryption metadata
    encryption_iv = models.BinaryField(
        max_length=16,
        help_text="Initialization vector for AES-GCM"
    )
    
    encryption_tag = models.BinaryField(
        max_length=16,
        help_text="Authentication tag for AES-GCM"
    )
    
    encryption_key_id = models.CharField(
        max_length=64,
        help_text="Identifier for the encryption key"
    )
    
    # =========================================================================
    # NON-SENSITIVE METADATA
    # =========================================================================
    
    media_type = models.CharField(
        max_length=20,
        choices=MediaType.CHOICES,
        db_index=True,
        help_text="Type of media"
    )
    
    mime_type = models.CharField(
        max_length=100,
        help_text="MIME type of original file"
    )
    
    file_size = models.PositiveIntegerField(
        help_text="Size of encrypted file in bytes"
    )
    
    original_size = models.PositiveIntegerField(
        help_text="Size of original file before encryption"
    )
    
    # Content hash (for deduplication and integrity)
    content_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 hash of encrypted content"
    )
    
    # Order in report (if multiple media)
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order within report"
    )
    
    # Processing status
    is_processed = models.BooleanField(
        default=False,
        help_text="Whether media has been processed (virus scan, etc.)"
    )
    
    is_clean = models.BooleanField(
        default=True,
        help_text="Whether media passed security scans"
    )
    
    processing_error = models.TextField(
        blank=True,
        help_text="Error message if processing failed"
    )
    
    # =========================================================================
    # METADATA FOR MEDIA (optional, from EXIF, etc.)
    # Stripped of identifying information
    # =========================================================================
    
    # Duration (for audio/video)
    duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration in seconds for audio/video"
    )
    
    # Dimensions (for images/video)
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Width in pixels"
    )
    
    height = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Height in pixels"
    )
    
    class Meta:
        db_table = 'report_media'
        verbose_name = 'Report Media'
        verbose_name_plural = 'Report Media'
        ordering = ['report', 'order', 'created_at']
        indexes = [
            models.Index(fields=['report', 'media_type']),
            models.Index(fields=['content_hash']),
        ]
    
    def __str__(self):
        return f"Media {self.id} for {self.report.report_number}"
    
    @classmethod
    def validate_media_type(cls, mime_type, file_size):
        """
        Validate that the media type is allowed and size is within limits.
        
        Returns:
            tuple: (is_valid, media_type, error_message)
        """
        # Find the media type for this MIME type
        for media_type, allowed_mimes in MediaType.ALLOWED_MIME_TYPES.items():
            if mime_type in allowed_mimes:
                # Check size
                max_size = MediaType.MAX_SIZES.get(media_type, 0)
                if file_size > max_size:
                    return (
                        False, 
                        media_type, 
                        f"File size exceeds maximum allowed ({max_size // (1024*1024)} MB)"
                    )
                return (True, media_type, None)
        
        return (False, None, f"File type not allowed: {mime_type}")
    
    def soft_delete(self, deleted_by=None):
        """
        Soft delete media.
        Note: Actual file is retained for audit compliance.
        """
        super().soft_delete()
        # Update report media count
        self.report.media_count = self.report.media_files.filter(is_deleted=False).count()
        self.report.save(update_fields=['media_count'])


class MediaAccessLog(models.Model):
    """
    Audit log for media access.
    
    Every access to media files is logged for compliance.
    This is separate from the main audit log for performance
    and specialized querying.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    media = models.ForeignKey(
        ReportMedia,
        on_delete=models.CASCADE,
        related_name='access_logs'
    )
    
    accessed_by_id = models.CharField(
        max_length=36,
        db_index=True,
        help_text="UUID of user who accessed (as string for immutability)"
    )
    
    accessed_by_role = models.CharField(
        max_length=20,
        help_text="Role at time of access"
    )
    
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True
    )
    
    access_type = models.CharField(
        max_length=20,
        choices=[
            ('view_metadata', 'View Metadata'),
            ('download', 'Download'),
            ('decrypt', 'Decrypt'),
        ],
        help_text="Type of access"
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    
    was_authorized = models.BooleanField(
        default=True,
        help_text="Whether access was authorized"
    )
    
    authorization_id = models.CharField(
        max_length=36,
        blank=True,
        help_text="UUID of decryption authorization if applicable"
    )
    
    class Meta:
        db_table = 'media_access_logs'
        verbose_name = 'Media Access Log'
        verbose_name_plural = 'Media Access Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['media', 'timestamp']),
            models.Index(fields=['accessed_by_id', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Access to {self.media_id} by {self.accessed_by_id} at {self.timestamp}"
    
    def save(self, *args, **kwargs):
        """Enforce append-only behavior."""
        if self.pk and MediaAccessLog.objects.filter(pk=self.pk).exists():
            raise PermissionError("Media access logs are immutable.")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion."""
        raise PermissionError("Media access logs cannot be deleted.")
