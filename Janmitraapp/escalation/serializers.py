"""
Escalation Serializers - For Report Escalations and Identity Reveal Requests
"""

from rest_framework import serializers

from .models import Escalation, IdentityRevealRequest
from authentication.models import User


class EscalationCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating escalation requests.
    
    Level 2 authorities can escalate reports to Level 1.
    """
    
    class Meta:
        model = Escalation
        fields = [
            'id',
            'report',
            'reason',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_report(self, value):
        """Ensure the report exists and is not already escalated."""
        # Check if report already has a pending or approved escalation
        existing = Escalation.objects.filter(
            report=value,
            status__in=[Escalation.STATUS_PENDING, Escalation.STATUS_APPROVED]
        ).exists()
        
        if existing:
            raise serializers.ValidationError(
                "This report already has a pending or approved escalation."
            )
        
        return value
    
    def create(self, validated_data):
        """Create escalation with the current user."""
        request = self.context.get('request')
        validated_data['escalated_by'] = request.user
        return super().create(validated_data)


class EscalationListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing escalations.
    """
    
    escalated_by_email = serializers.CharField(source='escalated_by.email', read_only=True)
    approved_by_email = serializers.CharField(
        source='approved_by.email', 
        read_only=True, 
        allow_null=True
    )
    report_title = serializers.CharField(source='report.title', read_only=True, allow_null=True)
    
    class Meta:
        model = Escalation
        fields = [
            'id',
            'report',
            'report_title',
            'escalated_by',
            'escalated_by_email',
            'approved_by',
            'approved_by_email',
            'reason',
            'status',
            'escalated_at',
            'resolved_at',
            'created_at',
        ]
        read_only_fields = fields


class EscalationDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for a single escalation.
    """
    
    escalated_by_email = serializers.CharField(source='escalated_by.email', read_only=True)
    approved_by_email = serializers.CharField(
        source='approved_by.email', 
        read_only=True, 
        allow_null=True
    )
    
    class Meta:
        model = Escalation
        fields = [
            'id',
            'report',
            'escalated_by',
            'escalated_by_email',
            'approved_by',
            'approved_by_email',
            'reason',
            'status',
            'escalated_at',
            'resolved_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class EscalationApproveSerializer(serializers.Serializer):
    """
    Serializer for approving/rejecting escalations.
    
    Only Level 1 authorities can approve or reject.
    """
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True)


# Identity Reveal Request Serializers

class IdentityRevealRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating identity reveal requests.
    
    Level 2 authorities can request identity reveals.
    """
    
    class Meta:
        model = IdentityRevealRequest
        fields = [
            'id',
            'report',
            'reveal_reason',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_report(self, value):
        """Ensure no pending request exists for this report."""
        existing = IdentityRevealRequest.objects.filter(
            report=value,
            status=IdentityRevealRequest.STATUS_PENDING
        ).exists()
        
        if existing:
            raise serializers.ValidationError(
                "This report already has a pending identity reveal request."
            )
        
        return value
    
    def validate_reveal_reason(self, value):
        """Ensure reason is substantial."""
        if len(value.strip()) < 50:
            raise serializers.ValidationError(
                "Reveal reason must be at least 50 characters to ensure proper justification."
            )
        return value
    
    def create(self, validated_data):
        """Create request with the current user."""
        request = self.context.get('request')
        validated_data['requested_by'] = request.user
        return super().create(validated_data)


class IdentityRevealRequestListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing identity reveal requests.
    """
    
    requested_by_email = serializers.CharField(source='requested_by.email', read_only=True)
    approved_by_level_1_email = serializers.CharField(
        source='approved_by_level_1.email', 
        read_only=True, 
        allow_null=True
    )
    
    class Meta:
        model = IdentityRevealRequest
        fields = [
            'id',
            'report',
            'requested_by',
            'requested_by_email',
            'status',
            'approved_by_level_1',
            'approved_by_level_1_email',
            'created_at',
        ]
        read_only_fields = fields


class IdentityRevealRequestDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for a single identity reveal request.
    """
    
    requested_by_email = serializers.CharField(source='requested_by.email', read_only=True)
    approved_by_level_1_email = serializers.CharField(
        source='approved_by_level_1.email', 
        read_only=True, 
        allow_null=True
    )
    revealed_identity = serializers.SerializerMethodField()
    
    class Meta:
        model = IdentityRevealRequest
        fields = [
            'id',
            'report',
            'requested_by',
            'requested_by_email',
            'reveal_reason',
            'status',
            'approved_by_level_1',
            'approved_by_level_1_email',
            'approved_at',
            'revealed_identity',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_revealed_identity(self, obj):
        """
        Return revealed identity only if request is approved.
        
        This is intentionally minimal - actual identity data
        should be retrieved through a separate secure endpoint.
        """
        if obj.status == IdentityRevealRequest.STATUS_APPROVED:
            return {
                'is_revealed': True,
                'message': 'Identity revealed. Access full details through secure endpoint.'
            }
        return {
            'is_revealed': False,
            'message': 'Identity not yet revealed.'
        }


class IdentityRevealApproveSerializer(serializers.Serializer):
    """
    Serializer for approving/rejecting identity reveal requests.
    
    Only Level 1 authorities can approve or reject.
    """
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True)
