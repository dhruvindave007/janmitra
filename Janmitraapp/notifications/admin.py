"""
Admin configuration for notifications.

READ-ONLY admin interface for notifications.
Notifications should only be created via the NotificationService.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Notification, NotificationType


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Admin for Notification model.
    
    READ-ONLY: Notifications are system-generated.
    """
    
    list_display = [
        'short_id',
        'recipient_display',
        'title_short',
        'notification_type_badge',
        'case_link',
        'level_badge',
        'is_read_badge',
        'created_at',
    ]
    list_filter = [
        'notification_type',
        'is_read',
        'level',
        'created_at',
    ]
    search_fields = [
        'id',
        'recipient__identifier',
        'title',
        'message',
        'case__id',
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    # All fields read-only
    readonly_fields = [
        'id',
        'recipient',
        'title',
        'message',
        'notification_type',
        'case',
        'level',
        'is_read',
        'read_at',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Notification', {
            'fields': ('id', 'recipient', 'notification_type'),
        }),
        ('Content', {
            'fields': ('title', 'message'),
        }),
        ('Context', {
            'fields': ('case', 'level'),
        }),
        ('Read Status', {
            'fields': ('is_read', 'read_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    # === Display helpers ===
    
    def short_id(self, obj):
        return str(obj.id)[:8] + '...'
    short_id.short_description = 'ID'
    short_id.admin_order_field = 'id'
    
    def recipient_display(self, obj):
        return obj.recipient.identifier if obj.recipient else '-'
    recipient_display.short_description = 'Recipient'
    recipient_display.admin_order_field = 'recipient__identifier'
    
    def title_short(self, obj):
        text = obj.title or ''
        return text[:40] + '...' if len(text) > 40 else text
    title_short.short_description = 'Title'
    
    def notification_type_badge(self, obj):
        colors = {
            NotificationType.NEW_CASE: '#3498db',
            NotificationType.CASE_ESCALATED: '#e67e22',
            NotificationType.CASE_SOLVED: '#27ae60',
            NotificationType.CASE_REJECTED: '#e74c3c',
            NotificationType.CASE_CLOSED: '#7f8c8d',
            NotificationType.SLA_WARNING: '#f1c40f',
            NotificationType.SLA_BREACHED: '#c0392b',
            NotificationType.ADMIN_ACTION: '#9b59b6',
            NotificationType.GENERAL: '#95a5a6',
        }
        color = colors.get(obj.notification_type, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 10px;">{}</span>',
            color, obj.get_notification_type_display()
        )
    notification_type_badge.short_description = 'Type'
    
    def case_link(self, obj):
        if obj.case:
            from django.urls import reverse
            url = reverse('admin:reports_case_change', args=[obj.case.id])
            return format_html('<a href="{}">Case: {}</a>', url, str(obj.case.id)[:8])
        return '-'
    case_link.short_description = 'Case'
    
    def level_badge(self, obj):
        if obj.level is None:
            return '-'
        colors = {
            2: '#9b59b6',
            1: '#e67e22',
            0: '#c0392b',
        }
        color = colors.get(obj.level, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 10px;">L{}</span>',
            color, obj.level
        )
    level_badge.short_description = 'Level'
    
    def is_read_badge(self, obj):
        if obj.is_read:
            return format_html(
                '<span style="color: #27ae60;">✓ Read</span>'
            )
        return format_html(
            '<span style="color: #e74c3c; font-weight: bold;">● Unread</span>'
        )
    is_read_badge.short_description = 'Status'
    
    # === Permissions (READ-ONLY) ===
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return True  # Allow viewing
    
    def has_delete_permission(self, request, obj=None):
        return False

