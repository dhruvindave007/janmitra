"""
Admin configuration for escalation models.
"""

from django.contrib import admin

from .models import Escalation, IdentityRevealRequest, DecryptionRequest


@admin.register(Escalation)
class EscalationAdmin(admin.ModelAdmin):
    """Admin for escalation requests."""
    
    list_display = ['report', 'escalated_by', 'status', 'priority', 'created_at', 'resolved_by']
    list_filter = ['status', 'priority', 'created_at']
    search_fields = ['report__id', 'report__report_number', 'escalated_by__identifier']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(IdentityRevealRequest)
class IdentityRevealRequestAdmin(admin.ModelAdmin):
    """Admin for identity reveal requests."""
    
    list_display = ['target_user', 'requested_by', 'status', 'urgency', 'reviewed_by', 'created_at']
    list_filter = ['status', 'urgency', 'created_at']
    search_fields = ['target_user__identifier', 'requested_by__identifier', 'case_reference']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(DecryptionRequest)
class DecryptionRequestAdmin(admin.ModelAdmin):
    """Admin for decryption requests."""
    
    list_display = ['report', 'requested_by', 'status', 'reviewed_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['report__id', 'report__report_number', 'requested_by__identifier']
    readonly_fields = ['id', 'created_at', 'updated_at']
