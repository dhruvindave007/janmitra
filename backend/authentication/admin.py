"""
Admin configuration for authentication models.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import User, JanMitraProfile, AuthorityProfile, DeviceSession, InviteCode


class AuthorityProfileInline(admin.StackedInline):
    """Inline for editing designation/department directly on User page."""
    model = AuthorityProfile
    fk_name = 'user'
    extra = 0
    max_num = 1
    fields = ['designation', 'department', 'jurisdiction_code', 'supervisor']
    verbose_name = 'Authority Profile'
    verbose_name_plural = 'Authority Profile'

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model with station assignment and designation."""
    
    list_display = [
        'identifier', 'role_badge', 'designation_display', 'police_station',
        'status_badge', 'is_active', 'has_device_token', 'created_at',
    ]
    list_filter = ['role', 'status', 'is_active', 'police_station']
    search_fields = ['identifier', 'id']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login', 'password_changed_at']
    filter_horizontal = ['assigned_stations', 'groups', 'user_permissions']
    list_per_page = 30
    list_select_related = ['police_station']
    inlines = [AuthorityProfileInline]
    
    fieldsets = (
        (None, {'fields': ('identifier', 'password')}),
        ('Role & Status', {'fields': ('role', 'status', 'is_anonymous')}),
        ('Station Assignment', {
            'fields': ('police_station', 'assigned_stations'),
            'description': 'police_station: Home station (L0–L2). assigned_stations: Regional stations (L3).',
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
            'description': 'is_active: Can log in. is_staff: Can access admin.',
        }),
        ('Device & FCM', {
            'fields': ('device_token',),
            'classes': ('collapse',),
        }),
        ('Security', {
            'fields': ('last_login', 'last_login_ip', 'failed_login_attempts', 'password_changed_at'),
            'classes': ('collapse',),
        }),
        ('Revocation', {
            'fields': ('revoked_at', 'revoked_by', 'revocation_reason'),
            'classes': ('collapse',),
        }),
        ('Advanced Permissions', {
            'fields': ('groups', 'user_permissions'),
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

    def role_badge(self, obj):
        colors = {
            'L0': '#3498db', 'L1': '#e67e22', 'L2': '#9b59b6',
            'L3': '#c0392b', 'L4': '#2c3e50', 'JANMITRA': '#27ae60',
        }
        color = colors.get(obj.role, '#95a5a6')
        label = obj.role
        if obj.role == 'JANMITRA':
            label = 'Citizen'
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; '
            'border-radius:3px; font-size:11px; font-weight:600;">{}</span>',
            color, label
        )
    role_badge.short_description = 'Role'
    role_badge.admin_order_field = 'role'

    def status_badge(self, obj):
        colors = {
            'active': '#27ae60', 'suspended': '#e67e22',
            'revoked': '#e74c3c', 'pending': '#95a5a6',
        }
        color = colors.get(obj.status, '#95a5a6')
        return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def designation_display(self, obj):
        try:
            return obj.authority_profile.designation or '-'
        except AuthorityProfile.DoesNotExist:
            return '-'
    designation_display.short_description = 'Designation'

    def has_device_token(self, obj):
        return bool(obj.device_token)
    has_device_token.boolean = True
    has_device_token.short_description = 'FCM'


# ── Keep registered but hidden from admin index ──────────────────────────────
# These are listed in HIDDEN_MODELS in admin_site.py so they don't appear
# on the dashboard, but remain accessible via direct URL.

@admin.register(JanMitraProfile)
class JanMitraProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'trust_score', 'total_reports_submitted', 'verified_reports_count', 'identity_revealed']
    list_filter = ['identity_revealed', 'trust_score']
    search_fields = ['user__identifier', 'user__id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'device_fingerprint_hash']


@admin.register(AuthorityProfile)
class AuthorityProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'department', 'jurisdiction_code', 'designation', 'created_at']
    list_filter = ['department']
    search_fields = ['user__identifier', 'jurisdiction_code', 'department', 'designation']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_active', 'created_at', 'last_activity_at', 'device_name']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__identifier', 'device_fingerprint_hash']
    readonly_fields = ['id', 'created_at', 'updated_at', 'device_fingerprint_hash']


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'issued_by', 'is_used', 'used_at', 'expires_at', 'created_at']
    list_filter = ['is_used', 'created_at']
    search_fields = ['code', 'issued_by__identifier']
    readonly_fields = ['id', 'created_at', 'updated_at']
