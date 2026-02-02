"""
Admin configuration for authentication models.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, JanMitraProfile, AuthorityProfile, DeviceSession, InviteCode


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model."""
    
    list_display = ['identifier', 'role', 'status', 'is_active', 'is_staff', 'created_at']
    list_filter = ['role', 'status', 'is_active', 'is_staff', 'created_at']
    search_fields = ['identifier', 'id']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login', 'password_changed_at']
    
    fieldsets = (
        (None, {'fields': ('identifier', 'password')}),
        ('Role & Status', {'fields': ('role', 'status', 'is_anonymous')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Security', {'fields': ('last_login', 'last_login_ip', 'failed_login_attempts', 'password_changed_at')}),
        ('Revocation', {'fields': ('revoked_at', 'revoked_by', 'revocation_reason')}),
        ('Timestamps', {'fields': ('id', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('identifier', 'password1', 'password2', 'role', 'status'),
        }),
    )


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
