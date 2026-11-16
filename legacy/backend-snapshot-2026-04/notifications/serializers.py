"""
Serializers for notifications.
"""

from rest_framework import serializers

from .models import Notification, NotificationType


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notification list/detail."""
    
    notification_type_display = serializers.CharField(
        source='get_notification_type_display',
        read_only=True
    )
    case_id = serializers.UUIDField(source='case.id', read_only=True, allow_null=True)
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'message',
            'notification_type',
            'notification_type_display',
            'case_id',
            'level',
            'is_read',
            'read_at',
            'created_at',
        ]
        read_only_fields = fields


class NotificationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for notification list."""
    
    notification_type_display = serializers.CharField(
        source='get_notification_type_display',
        read_only=True
    )
    case_id = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'notification_type',
            'notification_type_display',
            'case_id',
            'is_read',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_case_id(self, obj):
        return str(obj.case_id) if obj.case_id else None


class UnreadCountSerializer(serializers.Serializer):
    """Serializer for unread count response."""
    unread_count = serializers.IntegerField()
