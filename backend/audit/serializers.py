"""
Audit serializers.

Audit rows are append-only, so every serializer here is read-only.

``AuditLog`` and ``IdentityRevealLog`` deliberately hold no foreign keys:
actor and target are stored as plain id strings so a log entry survives
changes to (or removal of) the rows it describes. The serializers therefore
expose those stored columns directly rather than traversing relations.
"""

from rest_framework import serializers

from .models import AuditLog, IdentityRevealLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Full audit log entry."""

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'timestamp',
            'event_type',
            'severity',
            'success',
            'actor_id',
            'actor_role',
            'actor_identifier',
            'target_type',
            'target_id',
            'ip_address',
            'request_method',
            'request_path',
            'description',
            'metadata',
            'error_message',
        ]
        read_only_fields = fields


class AuditLogSummarySerializer(serializers.ModelSerializer):
    """Compact audit log entry for long listings."""

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'timestamp',
            'event_type',
            'severity',
            'success',
            'actor_identifier',
            'target_type',
            'target_id',
        ]
        read_only_fields = fields


class IdentityRevealLogSerializer(serializers.ModelSerializer):
    """Identity reveal log entry (the most sensitive audit record)."""

    class Meta:
        model = IdentityRevealLog
        fields = [
            'id',
            'timestamp',
            'janmitra_user_id',
            'revealed_to_user_id',
            'revealed_to_role',
            'approved_by_user_id',
            'related_report_id',
            'justification',
            'legal_authority',
            'ip_address',
        ]
        read_only_fields = fields
