"""
Admin configuration for core models.
"""

from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html

from .models import PoliceStation
from authentication.models import User


class StationOfficerInline(admin.TabularInline):
    """Read-only inline showing officers assigned to this station."""
    model = User
    fk_name = 'police_station'
    fields = ['identifier', 'role', 'status', 'is_active']
    readonly_fields = ['identifier', 'role', 'status', 'is_active']
    extra = 0
    max_num = 0  # No adding from inline
    verbose_name = 'Officer'
    verbose_name_plural = 'Station Officers'
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            is_deleted=False
        ).order_by('role', 'identifier')


@admin.register(PoliceStation)
class PoliceStationAdmin(admin.ModelAdmin):
    """Admin for PoliceStation — full CRUD with search, filters, and operational insights."""

    list_display = [
        'name',
        'code',
        'city',
        'district',
        'state',
        'coordinates_display',
        'is_active_badge',
        'officer_count_display',
        'active_officer_count_display',
        'case_count_display',
    ]
    list_filter = ['is_active', 'city', 'district', 'state']
    search_fields = ['name', 'code', 'city', 'district']
    ordering = ['state', 'district', 'city', 'name']
    list_per_page = 30
    inlines = [StationOfficerInline]

    readonly_fields = ['id', 'created_at', 'updated_at']

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'is_active'),
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'city', 'district', 'state'),
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _officer_count=Count(
                'officers', filter=Q(officers__is_deleted=False)
            ),
            _active_officer_count=Count(
                'officers', filter=Q(officers__is_deleted=False, officers__is_active=True)
            ),
            _case_count=Count('cases', filter=Q(cases__is_deleted=False)),
        )

    def coordinates_display(self, obj):
        return f'{obj.latitude}, {obj.longitude}'
    coordinates_display.short_description = 'Coordinates'

    def is_active_badge(self, obj):
        return obj.is_active
    is_active_badge.boolean = True
    is_active_badge.short_description = 'Active'

    def officer_count_display(self, obj):
        return getattr(obj, '_officer_count', 0)
    officer_count_display.short_description = 'Officers'
    officer_count_display.admin_order_field = '_officer_count'

    def active_officer_count_display(self, obj):
        count = getattr(obj, '_active_officer_count', 0)
        color = '#27ae60' if count > 0 else '#e74c3c'
        return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>', color, count
        )
    active_officer_count_display.short_description = 'Active Officers'
    active_officer_count_display.admin_order_field = '_active_officer_count'

    def case_count_display(self, obj):
        count = getattr(obj, '_case_count', 0)
        return format_html(
            '<span style="font-weight:600;">{}</span>', count
        )
    case_count_display.short_description = 'Cases'
    case_count_display.admin_order_field = '_case_count'
