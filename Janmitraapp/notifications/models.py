"""
Notification models for JanMitra Backend.

Provides:
- Notification model for authority alerts
- Read tracking
- Case linking

Design principles:
- No deletes allowed (soft delete via is_read)
- Ordered by newest first
- Linked to cases for context
"""

import uuid
from django.db import models
from django.utils import timezone

from core.models import BaseModel


class NotificationType:
    """Notification type constants."""
    NEW_CASE = 'new_case'
    CASE_ESCALATED = 'case_escalated'
    CASE_SOLVED = 'case_solved'
    CASE_REJECTED = 'case_rejected'
    CASE_CLOSED = 'case_closed'
    SLA_WARNING = 'sla_warning'
    SLA_BREACHED = 'sla_breached'
    ADMIN_ACTION = 'admin_action'
    GENERAL = 'general'
    
    CHOICES = [
        (NEW_CASE, 'New Case Assigned'),
        (CASE_ESCALATED, 'Case Escalated'),
        (CASE_SOLVED, 'Case Solved'),
        (CASE_REJECTED, 'Case Rejected'),
        (CASE_CLOSED, 'Case Closed'),
        (SLA_WARNING, 'SLA Warning'),
        (SLA_BREACHED, 'SLA Breached'),
        (ADMIN_ACTION, 'Admin Action'),
        (GENERAL, 'General'),
    ]


class NotificationManager(models.Manager):
    """Custom manager for notifications - prevents deletes."""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    
    def delete(self, *args, **kwargs):
        raise PermissionError("Notifications cannot be deleted.")


class Notification(BaseModel):
    """
    Notification model for authority users.
    
    Notifications are:
    - Linked to specific users (recipients)
    - Optionally linked to cases
    - Ordered newest first
    - Never deleted (only marked as read)
    """
    
    # Recipient (authority user)
    recipient = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="User who receives this notification"
    )
    
    # Notification content
    title = models.CharField(
        max_length=200,
        help_text="Short notification title"
    )
    
    message = models.TextField(
        help_text="Notification message body"
    )
    
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.CHOICES,
        default=NotificationType.GENERAL,
        db_index=True,
        help_text="Type of notification"
    )
    
    # Optional case link
    case = models.ForeignKey(
        'reports.Case',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="Related case (if applicable)"
    )
    
    # Level context (which level this notification is for)
    level = models.IntegerField(
        null=True,
        blank=True,
        help_text="Authority level this notification is for"
    )
    
    # Read tracking
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether the notification has been read"
    )
    
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the notification was read"
    )
    
    # Use custom manager
    objects = NotificationManager()
    all_objects = models.Manager()  # For admin access to all
    
    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"[{self.recipient.identifier}] {self.title}"
    
    def mark_as_read(self):
        """Mark this notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at', 'updated_at'])
    
    def delete(self, *args, **kwargs):
        """Prevent hard deletes - use soft delete instead."""
        self.is_deleted = True
        self.save(update_fields=['is_deleted', 'updated_at'])

