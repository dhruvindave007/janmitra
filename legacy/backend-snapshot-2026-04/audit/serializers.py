"""
Audit Serializers - Read-Only Serializers for Audit Logs

All audit data is read-only - no create, update, or delete operations.
"""

from rest_framework import serializers

from .models import AuditLog, IdentityRevealLog


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for audit log entries.
    
    Read-only serializer for viewing audit trail data.
    """
    
    actor_email = serializers.CharField(source='actor.email', read_only=True, allow_null=True)
    actor_role = serializers.CharField(source='actor.role', read_only=True, allow_null=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'created_at',
            'action',
            'actor',
            'actor_email',
            'actor_role',
            'resource_type',
            'resource_id',
            'ip_address',
            'device_fingerprint',
            'metadata',
        ]
        read_only_fields = fields


class AuditLogSummarySerializer(serializers.ModelSerializer):
    """
    Minimal serializer for audit log entries.
    
    Used for listing many audit entries efficiently.
    """
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'created_at',
            'action',
            'resource_type',
            'resource_id',
        ]
        read_only_fields = fields


class IdentityRevealLogSerializer(serializers.ModelSerializer):
    """
    Serializer for identity reveal log entries.
    
    Read-only serializer for viewing identity reveal audit trail.
    """
    
    report_id = serializers.UUIDField(source='reveal_request.report.id', read_only=True)
    requested_by_email = serializers.CharField(
        source='reveal_request.requested_by.email', 
        read_only=True,
        allow_null=True
    )
    approved_by_email = serializers.CharField(
        source='approved_by.email', 
        read_only=True,
        allow_null=True
    )
    approved_by_role = serializers.CharField(
        source='approved_by.role', 
        read_only=True,
        allow_null=True
    )
    reveal_reason = serializers.CharField(
        source='reveal_request.reveal_reason', 
        read_only=True
    )
    
    class Meta:
        model = IdentityRevealLog
        fields = [
            'id',
            'created_at',
            'reveal_request',
            'report_id',
            'revealed_anonymous_id',
            'revealed_to_user_id',
            'requested_by_email',
            'approved_by',
            'approved_by_email',
            'approved_by_role',
            'reveal_reason',
            'ip_address',
            'device_fingerprint',
        ]
        read_only_fields = fields
