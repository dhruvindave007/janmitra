"""
Admin configuration for authentication models.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, JanMitraProfile, AuthorityProfile, DeviceSession, InviteCode


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model with station assignment and designation."""
    
    list_display = [
        'identifier', 'role', 'designation_display', 'police_station',
        'status', 'is_active', 'has_device_token', 'created_at',
    ]
    list_filter = ['role', 'status', 'is_active', 'is_staff', 'police_station', 'created_at']
    search_fields = ['identifier', 'id']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login', 'password_changed_at']
    filter_horizontal = ['assigned_stations', 'groups', 'user_permissions']
    list_per_page = 30
    list_select_related = ['police_station']
    
    fieldsets = (
        (None, {'fields': ('identifier', 'password')}),
        ('Role & Status', {'fields': ('role', 'status', 'is_anonymous')}),
        ('Station Assignment', {
            'fields': ('police_station', 'assigned_stations'),
            'description': 'police_station: Home station (L0–L2). assigned_stations: Regional stations (L3).',
        }),
        ('Device', {
            'fields': ('device_token',),
            'classes': ('collapse',),
        }),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Security', {
            'fields': ('last_login', 'last_login_ip', 'failed_login_attempts', 'password_changed_at'),
            'classes': ('collapse',),
        }),
        ('Revocation', {
            'fields': ('revoked_at', 'revoked_by', 'revocation_reason'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('identifier', 'password1', 'password2', 'role', 'status', 'police_station'),
        }),
    )

    def designation_display(self, obj):
        """Show designation from AuthorityProfile if it exists."""
        try:
            return obj.authority_profile.designation or '-'
        except AuthorityProfile.DoesNotExist:
            return '-'
    designation_display.short_description = 'Designation'

    def has_device_token(self, obj):
        return bool(obj.device_token)
    has_device_token.boolean = True
    has_device_token.short_description = 'FCM'


@admin.register(JanMitraProfile)
class JanMitraProfileAdmin(admin.ModelAdmin):
    """Admin for JanMitra profiles."""
    
    list_display = ['user', 'trust_score', 'total_reports_submitted', 'verified_reports_count', 'identity_revealed']
    list_filter = ['identity_revealed', 'trust_score']
    search_fields = ['user__identifier', 'user__id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'device_fingerprint_hash']


@admin.register(AuthorityProfile)
class AuthorityProfileAdmin(admin.ModelAdmin):
    """Admin for authority profiles."""
    
    list_display = ['user', 'department', 'jurisdiction_code', 'designation', 'created_at']
    list_filter = ['department']
    search_fields = ['user__identifier', 'jurisdiction_code', 'department', 'designation']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    """Admin for device sessions."""
    
    list_display = ['user', 'is_active', 'created_at', 'last_activity_at', 'device_name']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__identifier', 'device_fingerprint_hash']
    readonly_fields = ['id', 'created_at', 'updated_at', 'device_fingerprint_hash']


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    """Admin for invite codes."""
    
    list_display = ['code', 'issued_by', 'is_used', 'used_at', 'expires_at', 'created_at']
    list_filter = ['is_used', 'created_at']
    search_fields = ['code', 'issued_by__identifier']
    readonly_fields = ['id', 'created_at', 'updated_at']
