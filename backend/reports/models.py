def visible_cases_for_user(user):
    qs = Case.objects.filter(is_deleted=False)
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
    OPEN = 'open'
    SOLVED = 'solved'
    REJECTED = 'rejected'
    CLOSED = 'closed'
    
    CHOICES = [
        (OPEN, 'Open'),
        (SOLVED, 'Solved'),
        (REJECTED, 'Rejected'),
        (CLOSED, 'Closed'),
    ]


class CaseLevel:
    """Case handling levels."""
    LEVEL_2 = 2  # Field Officers
    LEVEL_1 = 1  # Senior Officers
    LEVEL_0 = 0  # Highest Authority
    
    CHOICES = [
        (LEVEL_2, 'Level 2 - Field Officers'),
        (LEVEL_1, 'Level 1 - Senior Officers'),
        (LEVEL_0, 'Level 0 - Highest Authority'),
    ]


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
    
    A Case is created automatically when an Incident is submitted.
    Tracks the handling process through levels 2 -> 1 -> 0.
    """
    
    # Link to source incident
    incident = models.OneToOneField(
        Incident,
        on_delete=models.PROTECT,
        related_name='case',
        help_text="Source incident for this case"
    )
    
    # Current handling level
    current_level = models.IntegerField(
        choices=CaseLevel.CHOICES,
        default=CaseLevel.LEVEL_2,
        db_index=True,
        help_text="Current handling level (2=Field, 1=Senior, 0=Highest)"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=CaseStatus.CHOICES,
        default=CaseStatus.OPEN,
        db_index=True,
        help_text="Current case status"
    )
    
    # SLA tracking
    sla_deadline = models.DateTimeField(
        db_index=True,
        help_text="Deadline for current level to resolve before auto-escalation"
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
    
    class Meta:
        db_table = 'cases'
        verbose_name = 'Case'
        verbose_name_plural = 'Cases'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'current_level'], name='cases_status_9a5d6f_idx'),
            models.Index(fields=['sla_deadline'], name='cases_sla_dea_cee997_idx'),
            models.Index(fields=['current_level', 'status', 'sla_deadline'], name='cases_current_bc36d3_idx'),
        ]
    
    def __str__(self):
        return f"Case {self.id} - {self.status}"


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
    
    from_level = models.IntegerField(
        choices=CaseLevel.CHOICES,
        null=True,
        blank=True
    )
    
    to_level = models.IntegerField(
        choices=CaseLevel.CHOICES,
        null=True,
        blank=True
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


text_content = models.TextField(
    blank=True,
    null=True,
    help_text="Plain text report content"
)
