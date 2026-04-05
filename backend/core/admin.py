"""
Admin configuration for core models.
"""

from django.contrib import admin

from .models import PoliceStation


@admin.register(PoliceStation)
class PoliceStationAdmin(admin.ModelAdmin):
    """Admin for PoliceStation — full CRUD with search and filters."""

    list_display = [
        'name',
        'code',
        'city',
        'district',
        'state',
        'coordinates_display',
        'is_active_badge',
        'officer_count',
    ]
    list_filter = ['is_active', 'city', 'district', 'state']
    search_fields = ['name', 'code', 'city', 'district']
    ordering = ['state', 'district', 'city', 'name']
    list_per_page = 30

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

    def coordinates_display(self, obj):
        return f'{obj.latitude}, {obj.longitude}'
    coordinates_display.short_description = 'Coordinates'

    def is_active_badge(self, obj):
        return obj.is_active
    is_active_badge.boolean = True
    is_active_badge.short_description = 'Active'

    def officer_count(self, obj):
        return obj.officers.filter(is_deleted=False).count()
    officer_count.short_description = 'Officers'
