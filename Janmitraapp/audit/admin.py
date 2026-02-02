"""
Admin configuration for audit models.

Note: Audit logs are read-only in admin.
"""

from django.contrib import admin

from .models import AuditLog, IdentityRevealLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin for audit logs - read only."""
    
    list_display = ['event_type', 'actor_identifier', 'target_type', 'target_id', 'ip_address', 'timestamp']
    list_filter = ['event_type', 'severity', 'success', 'timestamp']
    search_fields = ['actor_identifier', 'target_id', 'ip_address', 'description']
    readonly_fields = ['id', 'timestamp', 'event_type', 'severity', 'actor_id', 'actor_role',
                       'actor_identifier', 'target_type', 'target_id', 'ip_address',
                       'user_agent', 'device_fingerprint_hash', 'request_method', 'request_path',
                       'description', 'metadata', 'success', 'error_message']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IdentityRevealLog)
class IdentityRevealLogAdmin(admin.ModelAdmin):
    """Admin for identity reveal logs - read only."""
    
    list_display = ['janmitra_user_id', 'revealed_to_user_id', 'approved_by_user_id', 'timestamp']
    list_filter = ['timestamp', 'revealed_to_role']
    search_fields = ['janmitra_user_id', 'revealed_to_user_id', 'approved_by_user_id']
    readonly_fields = ['id', 'timestamp', 'janmitra_user_id', 'revealed_to_user_id', 
                       'revealed_to_role', 'approved_by_user_id', 'related_report_id',
                       'justification', 'legal_authority', 'ip_address']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
