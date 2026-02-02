"""
Admin configuration for media storage models.
"""

from django.contrib import admin

from .models import ReportMedia, MediaAccessLog


@admin.register(ReportMedia)
class ReportMediaAdmin(admin.ModelAdmin):
    """Admin for report media attachments."""
    
    list_display = ['id', 'report', 'media_type', 'file_size', 'uploaded_by', 'created_at']
    list_filter = ['media_type', 'is_processed', 'is_clean', 'created_at']
    search_fields = ['report__id', 'content_hash']
    readonly_fields = ['id', 'created_at', 'updated_at', 'encrypted_file', 
                       'encryption_key_id', 'content_hash']


@admin.register(MediaAccessLog)
class MediaAccessLogAdmin(admin.ModelAdmin):
    """Admin for media access logs - read only."""
    
    list_display = ['media', 'accessed_by_id', 'access_type', 'ip_address', 'timestamp']
    list_filter = ['access_type', 'was_authorized', 'timestamp']
    search_fields = ['media__id', 'accessed_by_id', 'ip_address']
    readonly_fields = ['id', 'media', 'accessed_by_id', 'accessed_by_role',
                       'access_type', 'ip_address', 'was_authorized', 
                       'authorization_id', 'timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
