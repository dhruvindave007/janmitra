"""
Core models for JanMitra Backend.

Contains abstract base models that provide:
- UUID primary keys (no auto-increment IDs)
- Soft delete functionality
- Timestamp tracking
- Common audit fields

Also contains shared models:
- PoliceStation: Station registry for incident routing
"""

import uuid
from django.db import models
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    """
    Custom manager that excludes soft-deleted records by default.
    Use .all_with_deleted() to include deleted records.
    Use .deleted_only() to get only deleted records.
    """
    
    def get_queryset(self):
        """Return only non-deleted records by default."""
        return super().get_queryset().filter(is_deleted=False)
    
    def all_with_deleted(self):
        """Return all records including soft-deleted ones."""
        return super().get_queryset()
    
    def deleted_only(self):
        """Return only soft-deleted records."""
        return super().get_queryset().filter(is_deleted=True)


class BaseModel(models.Model):
    """
    Abstract base model providing UUID primary key and timestamps.
    
    All models in JanMitra MUST inherit from this class to ensure:
    1. UUID primary keys (required for security - no enumerable IDs)
    2. Consistent timestamp tracking
    3. Soft delete capability
    
    Security Note: UUIDs prevent enumeration attacks and don't reveal
    record count or creation order to potential attackers.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier (UUID v4)"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when record was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when record was last updated"
    )
    
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Soft delete flag - records are never physically deleted"
    )
    
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when record was soft-deleted"
    )
    
    # Custom manager for soft delete
    objects = SoftDeleteManager()
    all_objects = models.Manager()  # Fallback to access all records
    
    class Meta:
        abstract = True
        ordering = ['-created_at']
    
    def soft_delete(self):
        """
        Soft delete the record.
        Sets is_deleted=True and records deletion timestamp.
        """
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
    
    def restore(self):
        """
        Restore a soft-deleted record.
        """
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
    
    def hard_delete(self):
        """
        Permanently delete the record.
        
        WARNING: This should NEVER be used in production for sensitive data.
        Audit compliance requires data retention.
        """
        super().delete()
    
    def delete(self, *args, **kwargs):
        """
        Override default delete to perform soft delete.
        Use hard_delete() for actual deletion (discouraged).
        """
        self.soft_delete()


class AuditableModel(BaseModel):
    """
    Extended base model with audit trail fields.
    
    Use this for models that require tracking of who created/modified records.
    Inherits all BaseModel functionality plus adds user tracking.
    """
    
    created_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='%(class)s_created',
        null=True,
        blank=True,
        help_text="User who created this record"
    )
    
    updated_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='%(class)s_updated',
        null=True,
        blank=True,
        help_text="User who last updated this record"
    )
    
    deleted_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='%(class)s_deleted',
        null=True,
        blank=True,
        help_text="User who soft-deleted this record"
    )
    
    class Meta:
        abstract = True
    
    def soft_delete(self, deleted_by=None):
        """
        Soft delete with user tracking.
        """
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])


# =============================================================================
# POLICE STATION MODEL
# =============================================================================

class PoliceStation(BaseModel):
    """
    Police station registry for incident routing.
    
    Used to:
    - Route incidents to nearest station based on GPS
    - Route incidents to station based on area/zone mapping
    - Assign officers to stations
    - Filter cases by station
    
    Routing priority: area-name match → GPS haversine distance.
    """
    
    name = models.CharField(
        max_length=255,
        help_text="Station name"
    )
    
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique station code (e.g., PS-GJ-AHM-001)"
    )
    
    # GPS coordinates for nearest-station routing
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text="Station latitude coordinate"
    )
    
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text="Station longitude coordinate"
    )
    
    # Administrative hierarchy
    city = models.CharField(
        max_length=100,
        db_index=True,
        help_text="City name"
    )
    
    district = models.CharField(
        max_length=100,
        db_index=True,
        help_text="District name"
    )
    
    state = models.CharField(
        max_length=100,
        db_index=True,
        help_text="State name"
    )
    
    # Zone and jurisdiction
    zone = models.CharField(
        max_length=50,
        blank=True,
        default='',
        db_index=True,
        help_text="Police zone (e.g., Zone-1 East)"
    )
    
    jurisdiction_areas = models.TextField(
        blank=True,
        default='',
        help_text="Comma-separated area/locality names this station covers"
    )
    
    address = models.TextField(
        blank=True,
        default='',
        help_text="Full station address"
    )
    
    phone = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text="Station contact number"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether station is active and accepting cases"
    )
    
    class Meta:
        db_table = 'police_stations'
        verbose_name = 'Police Station'
        verbose_name_plural = 'Police Stations'
        ordering = ['state', 'district', 'city', 'name']
        indexes = [
            models.Index(fields=['latitude', 'longitude'], name='station_coords_idx'),
            models.Index(fields=['state', 'district', 'city'], name='station_hierarchy_idx'),
            models.Index(fields=['is_active', 'state'], name='station_active_state_idx'),
            models.Index(fields=['zone'], name='station_zone_idx'),
        ]
    
    def __str__(self):
        zone_str = f" [{self.zone}]" if self.zone else ""
        return f"{self.name} ({self.code}){zone_str}"
    
    def get_jurisdiction_area_list(self):
        """Return jurisdiction_areas as a list of lowercase area names."""
        if not self.jurisdiction_areas:
            return []
        return [a.strip().lower() for a in self.jurisdiction_areas.split(',') if a.strip()]
