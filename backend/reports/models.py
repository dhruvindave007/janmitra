def visible_cases_for_user(user):
    """
    Get cases visible to a user based on their role.
    
    Visibility rules:
    - L0: Only cases assigned to them
    - L1/L2: All cases at their police station
    - L3: Escalated cases (L3/L4 level) from their assigned stations
    - L4: All cases (full access)
    - JANMITRA: No access to case list
    """
    from authentication.models import UserRole
    
    qs = Case.objects.filter(is_deleted=False).select_related(
        'incident', 'incident__submitted_by', 'police_station', 'assigned_officer'
    )
    
    role = getattr(user, 'role', None)
    
    # New workflow roles
    if role == UserRole.L0:
        return qs.filter(assigned_officer=user)
    
    if role in [UserRole.L1, UserRole.L2]:
        station = getattr(user, 'police_station', None)
        if station:
            return qs.filter(police_station=station)
        return Case.objects.none()
    
    if role == UserRole.L3:
        # L3 sees escalated cases only from their assigned stations
        station_ids = user.assigned_stations.values_list('id', flat=True)
        if station_ids:
            return qs.filter(
                current_level__in=['L3', 'L4'],
                police_station_id__in=station_ids
            )
        return Case.objects.none()
    
    if role == UserRole.L4:
        # L4 has full access to all cases
        return qs
    
    if role == UserRole.JANMITRA:
        return Case.objects.none()
    
    # Legacy role handling (backward compatibility)
    if getattr(user, 'is_level_2', False) and not getattr(user, 'is_level_2_captain', False):
        return qs.filter(current_level=2)
    if getattr(user, 'is_level_2_captain', False):
        return qs.filter(current_level__gte=2)
    if getattr(user, 'is_level_1', False):
        return qs.filter(current_level=1)
    if getattr(user, 'is_level_0', False):
        return qs.filter(current_level=0)
    
    return Case.objects.none()


"""
Report models for JanMitra Backend.

Contains:
- Report: Encrypted intelligence reports from JanMitra members
- ReportAssignment: Assignment of reports to authorities
- ReportStatusHistory: Status change tracking

Security features:
- All report content is encrypted (client-side)
- Backend stores only encrypted blobs
- Decryption requires Level 1 approval
- Complete audit trail for all access
"""

import uuid
from django.db import models
from django.utils import timezone

from core.models import BaseModel, AuditableModel


class ReportStatus:
    """Report lifecycle status constants."""
    
    # Initial states
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    
    # Processing states
    RECEIVED = 'received'
    UNDER_REVIEW = 'under_review'
    PENDING_INFO = 'pending_info'
    
    # Escalation states
    ESCALATED = 'escalated'
    ESCALATION_PENDING = 'escalation_pending'
    
    # Resolution states
    VALIDATED = 'validated'
    ACTIONABLE = 'actionable'
    ACTION_TAKEN = 'action_taken'
    CLOSED = 'closed'
    
    # Rejection states
    REJECTED = 'rejected'
    INVALID = 'invalid'
    DUPLICATE = 'duplicate'
    
    CHOICES = [
        (DRAFT, 'Draft'),
        (SUBMITTED, 'Submitted'),
        (RECEIVED, 'Received'),
        (UNDER_REVIEW, 'Under Review'),
        (PENDING_INFO, 'Pending Additional Information'),
        (ESCALATED, 'Escalated'),
        (ESCALATION_PENDING, 'Escalation Pending'),
        (VALIDATED, 'Validated'),
        (ACTIONABLE, 'Actionable Intelligence'),
        (ACTION_TAKEN, 'Action Taken'),
        (CLOSED, 'Closed'),
        (REJECTED, 'Rejected'),
        (INVALID, 'Invalid'),
        (DUPLICATE, 'Duplicate'),
    ]
    
    # Statuses visible to JanMitra
    JANMITRA_VISIBLE = [
        SUBMITTED, RECEIVED, UNDER_REVIEW, PENDING_INFO,
        VALIDATED, ACTION_TAKEN, CLOSED, REJECTED, INVALID, DUPLICATE
    ]
    
    # Terminal states (no further status changes)
    TERMINAL_STATES = [CLOSED, REJECTED, INVALID, DUPLICATE]


class ReportPriority:
    """Report priority levels."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'
    
    CHOICES = [
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
        (CRITICAL, 'Critical'),
    ]


class ReportCategory:
    """
    Report category constants.
    Generic categories - not specific to any domain.
    """
    GENERAL = 'general'
    PUBLIC_SAFETY = 'public_safety'
    INFRASTRUCTURE = 'infrastructure'
    ENVIRONMENTAL = 'environmental'
    SOCIAL = 'social'
    ECONOMIC = 'economic'
    GOVERNANCE = 'governance'
    OTHER = 'other'
    
    CHOICES = [
        (GENERAL, 'General Intelligence'),
        (PUBLIC_SAFETY, 'Public Safety'),
        (INFRASTRUCTURE, 'Infrastructure'),
        (ENVIRONMENTAL, 'Environmental'),
        (SOCIAL, 'Social'),
        (ECONOMIC, 'Economic'),
        (GOVERNANCE, 'Governance'),
        (OTHER, 'Other'),
    ]


class Report(AuditableModel):
    """
    Encrypted intelligence report from JanMitra members.
    
    Security design:
    - Content is encrypted client-side before submission
    - Backend stores only encrypted blob
    - Encryption key is never transmitted to server
    - Decryption happens only on authorized devices
    
    Encryption approach:
    - AES-256-GCM for content encryption
    - Encryption key derived from user's secure storage
    - For lawful access: key escrow with Level 1 approval
    """
    
    # Report identification
    report_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        help_text="Human-readable report number (e.g., JM-2024-000001)"
    )
    
    # Submitter (JanMitra member)
    submitted_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='submitted_reports',
        help_text="JanMitra member who submitted the report"
    )
    
    # Submission timestamp
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When the report was submitted"
    )
    
    # =========================================================================
    # ENCRYPTED CONTENT
    # All sensitive content stored as encrypted blobs
    # =========================================================================
    
    # Encrypted report title
    encrypted_title = models.BinaryField(
        blank=True,
        null=True,
        help_text="AES-256-GCM encrypted title"
    )
    
    # Encrypted report content/description
    encrypted_content = models.BinaryField(
        blank=True,
        null=True,
        help_text="AES-256-GCM encrypted content"
    )
    
    # Encryption metadata (needed for decryption)
    encryption_iv = models.BinaryField(
        max_length=16,
        blank=True,
        null=True,
        help_text="Initialization vector for AES-GCM"
    )
    
    encryption_tag = models.BinaryField(
        max_length=16,
        blank=True,
        null=True,
        help_text="Authentication tag for AES-GCM"
    )
    
    # Key identifier for key management
    encryption_key_id = models.CharField(
        max_length=64,
        blank=True,
        help_text="Identifier for the encryption key (for key rotation)"
    )
    
    # =========================================================================
    # NON-SENSITIVE METADATA
    # This data is NOT encrypted - used for routing/filtering
    # =========================================================================
    
    status = models.CharField(
        max_length=30,
        choices=ReportStatus.CHOICES,
        default=ReportStatus.DRAFT,
        db_index=True,
        help_text="Current report status"
    )
    
    priority = models.CharField(
        max_length=20,
        choices=ReportPriority.CHOICES,
        default=ReportPriority.MEDIUM,
        db_index=True,
        help_text="Report priority level"
    )
    
    category = models.CharField(
        max_length=30,
        choices=ReportCategory.CHOICES,
        default=ReportCategory.GENERAL,
        db_index=True,
        help_text="Report category"
    )
    
    # Geographic context (non-sensitive metadata)
    jurisdiction_code = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Jurisdiction code for routing"
    )
    
    # Location (optional, stored as non-sensitive zone/area)
    location_zone = models.CharField(
        max_length=100,
        blank=True,
        help_text="General location zone (non-precise)"
    )
    
    # Timestamp of incident (if applicable)
    incident_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the reported incident occurred"
    )
    
    # =========================================================================
    # ASSIGNMENT AND HANDLING
    # =========================================================================
    
    # Current assignee
    assigned_to = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='assigned_reports',
        help_text="Currently assigned authority"
    )
    
    assigned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the report was assigned"
    )
    
    # Escalation tracking
    is_escalated = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether report has been escalated"
    )
    
    escalated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the report was escalated"
    )
    
    escalated_to = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='escalated_reports',
        help_text="Authority to whom report was escalated"
    )
    
    # =========================================================================
    # DECRYPTION CONTROL
    # =========================================================================
    
    decryption_authorized = models.BooleanField(
        default=False,
        help_text="Whether decryption has been authorized by Level 1"
    )
    
    decryption_authorized_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='decryption_authorizations',
        help_text="Level 1 authority who authorized decryption"
    )
    
    decryption_authorized_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When decryption was authorized"
    )
    
    decryption_reason = models.TextField(
        blank=True,
        help_text="Justification for decryption authorization"
    )
    
    # =========================================================================
    # RESOLUTION
    # =========================================================================
    
    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes about report resolution (not encrypted)"
    )
    
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the report was closed"
    )
    
    closed_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='closed_reports',
        help_text="Authority who closed the report"
    )
    
    # Media count (for quick reference)
    media_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of attached media files"
    )
    
    # Trust score at submission time (for reference)
    submitter_trust_score = models.PositiveSmallIntegerField(
        default=50,
        help_text="Submitter's trust score at time of submission"
    )
    
    class Meta:
        db_table = 'reports'
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['jurisdiction_code', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['submitted_by', 'submitted_at']),
        ]
    
    def __str__(self):
        return f"{self.report_number} ({self.status})"
    
    @classmethod
    def generate_report_number(cls):
        """
        Generate a unique report number.
        Format: JM-YYYY-NNNNNN
        """
        year = timezone.now().year
        prefix = f"JM-{year}-"
        
        # Get the latest report number for this year
        latest = cls.objects.filter(
            report_number__startswith=prefix
        ).order_by('-report_number').first()
        
        if latest:
            # Extract sequence number and increment
            try:
                seq = int(latest.report_number.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        
        return f"{prefix}{seq:06d}"
    
    def submit(self):
        """Submit a draft report."""
        if self.status != ReportStatus.DRAFT:
            raise ValueError("Only draft reports can be submitted")
        
        self.status = ReportStatus.SUBMITTED
        self.submitted_at = timezone.now()
        self.save()
    
    def assign_to(self, authority, assigned_by=None):
        """Assign report to an authority."""
        self.assigned_to = authority
        self.assigned_at = timezone.now()
        if self.status == ReportStatus.SUBMITTED:
            self.status = ReportStatus.RECEIVED
        self.save()
    
    def escalate(self, escalated_to, escalated_by):
        """Escalate report to higher authority."""
        self.is_escalated = True
        self.escalated_to = escalated_to
        self.escalated_at = timezone.now()
        self.status = ReportStatus.ESCALATED
        self.assigned_to = escalated_to
        self.assigned_at = timezone.now()
        self.save()
    
    def authorize_decryption(self, authorized_by, reason):
        """Authorize decryption of report content."""
        if not authorized_by.is_level_1:
            raise PermissionError("Only Level 1 can authorize decryption")
        
        self.decryption_authorized = True
        self.decryption_authorized_by = authorized_by
        self.decryption_authorized_at = timezone.now()
        self.decryption_reason = reason
        self.save()
    
    def close(self, closed_by, resolution_notes=''):
        """Close the report."""
        self.status = ReportStatus.CLOSED
        self.closed_at = timezone.now()
        self.closed_by = closed_by
        self.resolution_notes = resolution_notes
        self.save()


class ReportStatusHistory(BaseModel):
    """
    Track all status changes for a report.
    Provides complete audit trail of report lifecycle.
    """
    
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='status_history'
    )
    
    from_status = models.CharField(
        max_length=30,
        choices=ReportStatus.CHOICES,
        blank=True,
        help_text="Previous status"
    )
    
    to_status = models.CharField(
        max_length=30,
        choices=ReportStatus.CHOICES,
        help_text="New status"
    )
    
    changed_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='report_status_changes',
        help_text="User who changed the status"
    )
    
    reason = models.TextField(
        blank=True,
        help_text="Reason for status change"
    )
    
    class Meta:
        db_table = 'report_status_history'
        verbose_name = 'Report Status History'
        verbose_name_plural = 'Report Status Histories'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.report.report_number}: {self.from_status} → {self.to_status}"


class ReportNote(AuditableModel):
    """
    Internal notes on a report (by authorities).
    
    Notes are NOT encrypted as they are internal authority
    communications, not citizen-submitted content.
    """
    
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    
    author = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='report_notes'
    )
    
    content = models.TextField(
        help_text="Note content"
    )
    
    is_private = models.BooleanField(
        default=False,
        help_text="If true, only visible to same-level or higher authorities"
    )
    
    class Meta:
        db_table = 'report_notes'
        verbose_name = 'Report Note'
        verbose_name_plural = 'Report Notes'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note on {self.report.report_number} by {self.author}"


# =============================================================================
# INCIDENT / CASE LIFECYCLE MODELS (Step 2)
# =============================================================================

class IncidentCategory:
    """Incident category constants."""
    GENERAL = 'general'
    PUBLIC_SAFETY = 'public_safety'
    INFRASTRUCTURE = 'infrastructure'
    ENVIRONMENTAL = 'environmental'
    SOCIAL = 'social'
    ECONOMIC = 'economic'
    GOVERNANCE = 'governance'
    OTHER = 'other'
    
    CHOICES = [
        (GENERAL, 'General'),
        (PUBLIC_SAFETY, 'Public Safety'),
        (INFRASTRUCTURE, 'Infrastructure'),
        (ENVIRONMENTAL, 'Environmental'),
        (SOCIAL, 'Social'),
        (ECONOMIC, 'Economic'),
        (GOVERNANCE, 'Governance'),
        (OTHER, 'Other'),
    ]


class CaseStatus:
    """Case lifecycle status constants."""
    NEW = 'new'
    ASSIGNED = 'assigned'
    IN_PROGRESS = 'in_progress'
    ESCALATED = 'escalated'
    RESOLVED = 'resolved'
    OPEN = 'open'  # Legacy
    SOLVED = 'solved'
    REJECTED = 'rejected'
    CLOSED = 'closed'
    
    CHOICES = [
        (NEW, 'New'),
        (ASSIGNED, 'Assigned'),
        (IN_PROGRESS, 'In Progress'),
        (ESCALATED, 'Escalated'),
        (RESOLVED, 'Resolved'),
        (OPEN, 'Open'),
        (SOLVED, 'Solved'),
        (REJECTED, 'Rejected'),
        (CLOSED, 'Closed'),
    ]
    
    # Terminal states
    TERMINAL_STATES = [RESOLVED, CLOSED, REJECTED]


class CaseLevel:
    """
    Case handling levels (New Workflow).
    
    Levels flow: L0/L1/L2 (station) → L3 (higher) → L4 (top)
    """
    L0 = 'L0'   # Field Officer (assigned by L1)
    L1 = 'L1'   # PSO
    L2 = 'L2'   # PI
    L3 = 'L3'   # Higher Authority (first escalation)
    L4 = 'L4'   # Top Authority (final escalation, no SLA)
    
    # Legacy levels for backward compatibility
    LEVEL_2 = 2  # Field Officers
    LEVEL_1 = 1  # Senior Officers
    LEVEL_0 = 0  # Highest Authority
    
    CHOICES = [
        # New workflow levels
        (L0, 'L0 - Field Officer'),
        (L1, 'L1 - PSO'),
        (L2, 'L2 - PI'),
        (L3, 'L3 - Higher Authority'),
        (L4, 'L4 - Top Authority'),
        # Legacy choices (kept for backward compatibility)
        (LEVEL_2, 'Level 2 - Field Officers (Legacy)'),
        (LEVEL_1, 'Level 1 - Senior Officers (Legacy)'),
        (LEVEL_0, 'Level 0 - Highest Authority (Legacy)'),
    ]
    
    # Station-level (subject to 48h SLA, escalates to L3)
    STATION_LEVELS = [L0, L1, L2]
    
    # Escalation levels (L3 has SLA, L4 does not)
    ESCALATION_LEVELS = [L3, L4]


class Incident(BaseModel):
    """
    Immutable incident submission from JanMitra member.
    
    An incident is the original submission that cannot be modified.
    A Case is created automatically to track the lifecycle.
    """
    
    # Submitter
    submitted_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='incidents',
        help_text="JanMitra member who submitted this incident"
    )
    
    # Content
    text_content = models.TextField(
        help_text="Incident description text (required)"
    )
    
    category = models.CharField(
        max_length=30,
        choices=IncidentCategory.CHOICES,
        default=IncidentCategory.GENERAL,
        db_index=True,
        help_text="Incident category"
    )
    
    # Location (optional)
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text="Latitude coordinate (optional)"
    )
    
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text="Longitude coordinate (optional)"
    )
    
    # Area metadata (resolved from coordinates - for future routing)
    area_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Resolved area/locality name"
    )
    
    city = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="City name"
    )
    
    state = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="State name"
    )
    
    class Meta:
        db_table = 'incidents'
        verbose_name = 'Incident'
        verbose_name_plural = 'Incidents'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Incident {self.id} - {self.category}"
    
    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None


# =============================================================================
# INCIDENT MEDIA
# =============================================================================

class IncidentMediaType:
    """Media type constants for incident attachments."""
    PHOTO = 'photo'
    VIDEO = 'video'
    
    CHOICES = [
        (PHOTO, 'Photo'),
        (VIDEO, 'Video'),
    ]
    
    # Allowed MIME types per category
    ALLOWED_MIME_TYPES = {
        PHOTO: [
            'image/jpeg',
            'image/png',
            'image/webp',
            'image/heic',
            'image/heif',
        ],
        VIDEO: [
            'video/mp4',
            'video/quicktime',
            'video/webm',
        ],
    }
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = {
        PHOTO: ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'],
        VIDEO: ['.mp4', '.mov', '.webm'],
    }
    
    # Maximum file sizes in bytes
    MAX_SIZES = {
        PHOTO: 10 * 1024 * 1024,      # 10 MB
        VIDEO: 50 * 1024 * 1024,      # 50 MB
    }
    
    # Maximum files per incident
    MAX_FILES_PER_INCIDENT = 3


def incident_media_path(instance, filename):
    """
    Generate secure storage path for incident media.
    
    Path format: incident_media/<incident_uuid>/<media_uuid>.<ext>
    
    Organized by incident for easy cleanup and access control.
    Original filename is NOT used to prevent information leakage.
    """
    import os
    ext = os.path.splitext(filename)[1].lower() or '.bin'
    return os.path.join(
        'incident_media',
        str(instance.incident_id),
        f"{instance.id}{ext}"
    )


class IncidentMedia(BaseModel):
    """
    Media attachment for an incident.
    
    Security design:
    - Files stored in private directory (not publicly accessible)
    - Access requires authentication
    - JanMitra cannot view after submission
    - Only Level-2+ authorities can view
    - Admin has download access
    - Maximum 3 files per incident
    """
    
    # Link to incident
    incident = models.ForeignKey(
        Incident,
        on_delete=models.PROTECT,
        related_name='media_files',
        help_text="Incident this media belongs to"
    )
    
    # The actual file
    file = models.FileField(
        upload_to=incident_media_path,
        help_text="Uploaded media file"
    )
    
    # Media type
    media_type = models.CharField(
        max_length=10,
        choices=IncidentMediaType.CHOICES,
        db_index=True,
        help_text="Type of media (photo/video)"
    )
    
    # Original filename (for reference, not used in storage)
    original_filename = models.CharField(
        max_length=255,
        blank=True,
        help_text="Original filename (for reference only)"
    )
    
    # File metadata
    file_size = models.PositiveIntegerField(
        default=0,
        help_text="File size in bytes"
    )
    
    content_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="MIME type of the file"
    )
    
    # Uploader
    uploaded_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='uploaded_incident_media',
        help_text="User who uploaded this media"
    )
    
    class Meta:
        db_table = 'incident_media'
        verbose_name = 'Incident Media'
        verbose_name_plural = 'Incident Media'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['incident', 'created_at']),
        ]
    
    def __str__(self):
        return f"Media {self.id} for Incident {self.incident_id}"
    
    def delete(self, *args, **kwargs):
        """Prevent deletion - use soft delete only."""
        self.is_deleted = True
        self.save(update_fields=['is_deleted', 'updated_at'])
    
    @classmethod
    def get_count_for_incident(cls, incident_id):
        """Get number of media files for an incident."""
        return cls.objects.filter(incident_id=incident_id, is_deleted=False).count()


class Case(BaseModel):
    """
    Managed case lifecycle with SLA tracking.
    
    New workflow:
    - Case routed to PoliceStation based on nearest GPS
    - L1 assigns L0 officer
    - L0 works case, L2 closes
    - 48h SLA → auto-escalate to L3 → L4
    
    A Case is created automatically when an Incident is submitted.
    """
    
    # Link to source incident
    incident = models.OneToOneField(
        Incident,
        on_delete=models.PROTECT,
        related_name='case',
        help_text="Source incident for this case"
    )
    
    # Assigned police station (new workflow)
    police_station = models.ForeignKey(
        'core.PoliceStation',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='cases',
        help_text="Police station this case is routed to"
    )
    
    # Current handling level (new workflow uses string levels)
    current_level = models.CharField(
        max_length=10,
        choices=[
            ('L0', 'L0 - Field Officer'),
            ('L1', 'L1 - PSO'),
            ('L2', 'L2 - PI'),
            ('L3', 'L3 - Higher Authority'),
            ('L4', 'L4 - Top Authority'),
        ],
        default='L1',
        db_index=True,
        help_text="Current handling level (L0/L1/L2/L3/L4)"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('new', 'New'),
            ('assigned', 'Assigned'),
            ('in_progress', 'In Progress'),
            ('escalated', 'Escalated'),
            ('resolved', 'Resolved'),
            ('open', 'Open'),
            ('solved', 'Solved'),
            ('rejected', 'Rejected'),
            ('closed', 'Closed'),
        ],
        default='new',
        db_index=True,
        help_text="Current case status"
    )
    
    # Officer assignment (L1 assigns L0)
    assigned_officer = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='assigned_cases',
        help_text="L0 officer assigned to this case"
    )
    
    assigned_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='case_assignments_made',
        help_text="L1 who assigned the officer"
    )
    
    assigned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When officer was assigned"
    )
    
    # SLA tracking
    sla_deadline = models.DateTimeField(
        db_index=True,
        help_text="Deadline for resolution before auto-escalation (48h)"
    )
    
    sla_breached_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When SLA was breached (null if not breached)"
    )
    
    # Resolution tracking
    solved_at = models.DateTimeField(null=True, blank=True)
    solved_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='cases_solved'
    )
    solution_notes = models.TextField(blank=True)
    
    # Closure tracking (L2 closes cases solved by L0)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='cases_closed'
    )
    closed_by_level = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="Level of the user who closed the case"
    )
    
    # Rejection tracking
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='cases_rejected'
    )
    rejection_reason = models.TextField(blank=True)
    
    # Escalation tracking
    escalation_count = models.PositiveSmallIntegerField(default=0)
    last_escalated_at = models.DateTimeField(null=True, blank=True)
    
    # Investigation chat lock
    is_chat_locked = models.BooleanField(
        default=False,
        help_text="Whether investigation chat is locked (after case closure)"
    )
    
    class Meta:
        db_table = 'cases'
        verbose_name = 'Case'
        verbose_name_plural = 'Cases'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'current_level'], name='cases_status_9a5d6f_idx'),
            models.Index(fields=['sla_deadline'], name='cases_sla_dea_cee997_idx'),
            models.Index(fields=['current_level', 'status', 'sla_deadline'], name='cases_current_bc36d3_idx'),
            models.Index(fields=['police_station', 'status'], name='case_station_status_idx'),
            models.Index(fields=['police_station', 'current_level', 'status'], name='case_station_level_idx'),
            models.Index(fields=['assigned_officer', 'status'], name='case_officer_status_idx'),
            models.Index(fields=['sla_breached_at'], name='case_sla_breach_idx'),
        ]
    
    # Level ordering for monotonic enforcement
    # L0/L1/L2 are station levels (can transition between them)
    # L3/L4 are escalated levels (once reached, cannot decrease)
    LEVEL_ORDER = {'L0': 0, 'L1': 1, 'L2': 2, 'L3': 3, 'L4': 4}
    ESCALATED_LEVELS = {'L3', 'L4'}
    
    def __str__(self):
        return f"Case {self.id} - {self.status}"
    
    def save(self, *args, **kwargs):
        """
        Override save to enforce monotonic level for escalated cases.
        Once a case reaches L3 or L4, the level cannot decrease.
        Station levels (L0/L1/L2) can transition freely before escalation.
        """
        if not self._state.adding:
            # Get the current level from database
            try:
                old_case = Case.objects.get(pk=self.pk)
                old_level_str = old_case.current_level
                new_level_str = self.current_level
                
                # If case was at L3 or L4, enforce monotonic increase
                if old_level_str in self.ESCALATED_LEVELS:
                    old_level = self.LEVEL_ORDER.get(old_level_str, 0)
                    new_level = self.LEVEL_ORDER.get(new_level_str, 0)
                    
                    # Cannot decrease from escalated level
                    if new_level < old_level:
                        self.current_level = old_level_str
            except Case.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)


class CaseNote(BaseModel):
    """
    Append-only notes on a case by officers.
    """
    
    case = models.ForeignKey(
        Case,
        on_delete=models.PROTECT,
        related_name='notes',
        help_text="Case this note belongs to"
    )
    
    author = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='case_notes',
        help_text="Officer who wrote this note"
    )
    
    author_level = models.CharField(
        max_length=10,
        help_text="Author's role level at time of note creation"
    )
    
    note_text = models.TextField(
        help_text="Note content"
    )
    
    class Meta:
        db_table = 'case_notes'
        verbose_name = 'Case Note'
        verbose_name_plural = 'Case Notes'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note on Case {self.case_id} by {self.author}"


class CaseStatusHistory(BaseModel):
    """
    Immutable status change history for a case.
    """
    
    case = models.ForeignKey(
        Case,
        on_delete=models.PROTECT,
        related_name='status_history',
        help_text="Case this history entry belongs to"
    )
    
    from_status = models.CharField(
        max_length=20,
        choices=CaseStatus.CHOICES,
        blank=True,
        null=True,
        help_text="Previous status (null for initial creation)"
    )
    
    to_status = models.CharField(
        max_length=20,
        choices=CaseStatus.CHOICES,
        help_text="New status"
    )
    
    from_level = models.CharField(
        max_length=10,
        choices=CaseLevel.CHOICES,
        null=True,
        blank=True,
        help_text="Previous level (L0/L1/L2/L3/L4)"
    )
    
    to_level = models.CharField(
        max_length=10,
        choices=CaseLevel.CHOICES,
        null=True,
        blank=True,
        help_text="New level (L0/L1/L2/L3/L4)"
    )
    
    changed_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='case_status_changes',
        help_text="User who changed the status (null for system/auto-escalation)"
    )
    
    reason = models.TextField(blank=True)
    
    is_auto_escalation = models.BooleanField(
        default=False,
        help_text="True if this was an automatic SLA-based escalation"
    )
    
    class Meta:
        db_table = 'case_status_history'
        verbose_name = 'Case Status History'
        verbose_name_plural = 'Case Status Histories'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Case {self.case_id}: {self.from_status} -> {self.to_status}"
    
    def save(self, *args, **kwargs):
        """Prevent updates after creation (immutable)."""
        if not self._state.adding:
            raise PermissionError("Case status history records are immutable.")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion - history records are immutable."""
        raise PermissionError("Case status history records cannot be deleted.")


# =============================================================================
# INVESTIGATION CHAT MODELS (New Workflow)
# =============================================================================

class MessageType:
    """Investigation message type constants."""
    TEXT = 'text'
    MEDIA = 'media'
    SYSTEM = 'system'
    
    CHOICES = [
        (TEXT, 'Text Message'),
        (MEDIA, 'Media Message'),
        (SYSTEM, 'System Message'),
    ]


def investigation_media_path(instance, filename):
    """
    Generate secure storage path for investigation media.
    
    Path format: investigation_media/<case_uuid>/<message_uuid>.<ext>
    """
    import os
    ext = os.path.splitext(filename)[1].lower() or '.bin'
    return os.path.join(
        'investigation_media',
        str(instance.case_id),
        f"{instance.id}{ext}"
    )


class InvestigationMessage(BaseModel):
    """
    Immutable chat message in case investigation.
    
    Design principles:
    - Case IS the thread (no separate thread model)
    - Messages are immutable (no edit after creation)
    - Media embedded in message (no separate media model)
    - System messages for automated events
    - Locked when case is closed
    
    Access control:
    - L0: Only if assigned to case
    - L1/L2: If case is at their station
    - L3/L4: If case is escalated to their level
    """
    
    # Parent case (acts as thread)
    case = models.ForeignKey(
        Case,
        on_delete=models.PROTECT,
        related_name='investigation_messages',
        help_text="Case this message belongs to"
    )
    
    # Sender (null for system messages)
    sender = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='investigation_messages_sent',
        help_text="User who sent this message (null for system)"
    )
    
    # Snapshot of sender's role at message creation
    sender_role = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Sender's role at time of sending (L0/L1/L2/L3/L4/SYSTEM)"
    )
    
    # Message type
    message_type = models.CharField(
        max_length=10,
        choices=MessageType.CHOICES,
        default=MessageType.TEXT,
        db_index=True,
        help_text="Type of message"
    )
    
    # Text content (for text and media-with-caption messages)
    text_content = models.TextField(
        blank=True,
        null=True,
        help_text="Message text content"
    )
    
    # Media attachment (for media messages)
    file = models.FileField(
        upload_to=investigation_media_path,
        blank=True,
        null=True,
        help_text="Attached media file"
    )
    
    file_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Original filename"
    )
    
    file_size = models.BigIntegerField(
        blank=True,
        null=True,
        help_text="File size in bytes"
    )
    
    file_type = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="MIME type of the file"
    )
    
    class Meta:
        db_table = 'investigation_messages'
        verbose_name = 'Investigation Message'
        verbose_name_plural = 'Investigation Messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['case', 'created_at'], name='inv_msg_case_time_idx'),
            models.Index(fields=['sender'], name='inv_msg_sender_idx'),
            models.Index(fields=['created_at'], name='inv_msg_created_idx'),
        ]
    
    def __str__(self):
        sender_str = self.sender.identifier if self.sender else 'SYSTEM'
        return f"Message in Case {self.case_id} by {sender_str}"
    
    @property
    def content_type(self):
        """Alias for file_type (MIME type)."""
        return self.file_type
    
    def save(self, *args, **kwargs):
        """Prevent updates after creation (immutable)."""
        if not self._state.adding:
            # Allow only soft-delete updates
            update_fields = kwargs.get('update_fields')
            if update_fields and set(update_fields) <= {'is_deleted', 'deleted_at', 'updated_at'}:
                super().save(*args, **kwargs)
                return
            raise PermissionError("Investigation messages are immutable and cannot be edited.")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent hard deletion - use soft_delete() instead."""
        raise PermissionError("Investigation messages cannot be hard deleted. Use soft_delete() instead.")
    
    def soft_delete(self, deleted_by):
        """
        Soft delete message. Only the author can delete their own message.
        System messages cannot be deleted.
        
        Args:
            deleted_by: User attempting to delete the message
            
        Raises:
            PermissionError: If user is not the author or message is a system message
        """
        from django.utils import timezone
        
        # System messages cannot be deleted
        if self.message_type == 'system':
            raise PermissionError("System messages cannot be deleted.")
        
        # Only author can delete their own message
        if self.sender != deleted_by:
            raise PermissionError("Only the message author can delete their message.")
        
        # Perform soft delete
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])


# =============================================================================
# ESCALATION HISTORY (New Workflow)
# =============================================================================

class EscalationType:
    """Escalation type constants."""
    AUTO = 'auto'
    MANUAL = 'manual'
    
    CHOICES = [
        (AUTO, 'Automatic (SLA Breach)'),
        (MANUAL, 'Manual Escalation'),
    ]


class EventType:
    """Event type constants for EscalationHistory."""
    ESCALATION = 'escalation'
    ASSIGNMENT = 'assignment'
    
    CHOICES = [
        (ESCALATION, 'Escalation'),
        (ASSIGNMENT, 'Assignment'),
    ]


class EscalationHistory(BaseModel):
    """
    Audit trail for case escalation events.
    
    Records both:
    - Automatic escalations (SLA breach)
    - Manual escalations (officer-initiated)
    
    Immutable - no updates or deletes allowed.
    """
    
    case = models.ForeignKey(
        Case,
        on_delete=models.PROTECT,
        related_name='escalation_history',
        help_text="Case that was escalated"
    )
    
    # Event type (escalation vs assignment)
    event_type = models.CharField(
        max_length=15,
        choices=EventType.CHOICES,
        default=EventType.ESCALATION,
        db_index=True,
        help_text="Type of event (escalation or assignment)"
    )
    
    from_level = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="Level before escalation (L0/L1/L2/L3)"
    )
    
    to_level = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="Level after escalation (L3/L4)"
    )
    
    escalation_type = models.CharField(
        max_length=10,
        choices=EscalationType.CHOICES,
        blank=True,
        null=True,
        db_index=True,
        help_text="Type of escalation (only for escalation events)"
    )
    
    # Null for auto-escalations
    escalated_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='escalations_initiated',
        help_text="User who initiated escalation (null for auto)"
    )
    
    # For assignment events
    assigned_officer = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='assignment_history',
        help_text="Officer assigned (for assignment events)"
    )
    
    reason = models.TextField(
        blank=True,
        help_text="Reason for escalation or assignment notes"
    )
    
    class Meta:
        db_table = 'escalation_history'
        verbose_name = 'Escalation History'
        verbose_name_plural = 'Escalation Histories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['case', 'created_at'], name='esc_hist_case_time_idx'),
            models.Index(fields=['event_type'], name='esc_hist_event_type_idx'),
            models.Index(fields=['escalation_type'], name='esc_hist_type_idx'),
        ]
    
    def __str__(self):
        if self.event_type == EventType.ASSIGNMENT:
            return f"Case {self.case_id}: Assignment to {self.assigned_officer}"
        return f"Case {self.case_id}: {self.from_level} -> {self.to_level} ({self.escalation_type})"
    
    def save(self, *args, **kwargs):
        """Prevent updates after creation (immutable)."""
        if not self._state.adding:
            raise PermissionError("Escalation history records are immutable.")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion - history records are immutable."""
        raise PermissionError("Escalation history records cannot be deleted.")


text_content = models.TextField(
    blank=True,
    null=True,
    help_text="Plain text report content"
)
