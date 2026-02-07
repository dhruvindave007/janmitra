"""
Admin configuration for Core app.

Manages system-level configuration like app versions and updates.
"""
from django.contrib import admin
from django.utils.html import format_html
from core.models import AppVersion


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    """
    Admin interface for managing app versions.
    
    Allows uploading APK files and toggling between versions.
    Only one version should be active at a time.
    """
    
    list_display = [
        'version_display',
        'latest_version',
        'minimum_supported_version',
        'has_apk_file',
        'is_active_badge',
        'created_at',
    ]
    
    list_filter = ['is_active', 'created_at', 'updated_at']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at', 'apk_file_display']
    search_fields = ['latest_version', 'minimum_supported_version']
    
    fieldsets = (
        ('Version Information', {
            'fields': ('latest_version', 'minimum_supported_version'),
            'description': 'Define the latest and minimum supported versions.',
        }),
        ('APK Distribution', {
            'fields': ('apk_file', 'apk_file_display'),
            'description': 'Upload APK file for distribution. Files are stored in media/app_updates/ and served via MEDIA_URL.',
        }),
        ('Status', {
            'fields': ('is_active',),
            'description': 'Only the active version is returned by the API endpoint.',
        }),
        ('System Fields', {
            'fields': ('id', 'created_at', 'updated_at', 'deleted_at', 'is_deleted'),
            'classes': ('collapse',),
        }),
    )
    
    actions = ['activate_version', 'deactivate_version']
    
    def version_display(self, obj):
        """Display version in format v1.2.3."""
        return f"v{obj.latest_version}"
    version_display.short_description = 'Version'
    version_display.admin_order_field = 'latest_version'
    
    def has_apk_file(self, obj):
        """Show checkmark if APK file is present."""
        if obj.apk_file:
            return format_html(
                '<a href="{}" target="_blank" title="Download APK">✓ {}</a>',
                obj.apk_file.url,
                obj.apk_file.name.split('/')[-1]
            )
        return format_html('<span style="color: red;">✗ No file</span>')
    has_apk_file.short_description = 'APK File'
    
    def is_active_badge(self, obj):
        """Display active status as colored badge."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 3px;">Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    is_active_badge.admin_order_field = 'is_active'
    
    def apk_file_display(self, obj):
        """Display APK file info in readonly format."""
        if not obj.apk_file:
            return "No APK file uploaded"
        return format_html(
            '<a href="{}" target="_blank" download>Download: {}</a> ({})',
            obj.apk_file.url,
            obj.apk_file.name,
            self.get_file_size(obj.apk_file.size) if obj.apk_file.size else "Unknown size"
        )
    apk_file_display.short_description = 'APK File Info'
    
    @staticmethod
    def get_file_size(size_bytes):
        """Convert bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"
    
    def activate_version(self, request, queryset):
        """Deactivate all versions, then activate the selected one."""
        if queryset.count() != 1:
            self.message_user(request, 'Please select exactly one version to activate.', level='error')
            return
        
        version = queryset.first()
        AppVersion.objects.filter(is_active=True).update(is_active=False)
        version.is_active = True
        version.save(update_fields=['is_active', 'updated_at'])
        
        self.message_user(
            request,
            f'Version {version.latest_version} is now active and will be served by the API.'
        )
    activate_version.short_description = 'Activate selected version'
    
    def deactivate_version(self, request, queryset):
        """Deactivate selected versions."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} version(s) deactivated.')
    deactivate_version.short_description = 'Deactivate selected versions'
    
    def get_readonly_fields(self, request, obj=None):
        """Make version fields read-only for existing versions."""
        readonly = list(self.readonly_fields)
        if obj:  # Editing existing object
            readonly.extend(['latest_version', 'minimum_supported_version'])
        return readonly

