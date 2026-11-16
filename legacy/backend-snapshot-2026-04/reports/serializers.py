"""
Serializers for JanMitra Reports.

Handles:
- Report creation with encrypted content
- Report listing (different views for roles)
- Report status updates
- Validation and rejection

Security notes:
- Encrypted content is stored as binary
- Base64 encoding used for API transport
- Decryption authorization checked before revealing content
"""

import base64
from rest_framework import serializers
from django.utils import timezone

from .models import (
    Report, ReportStatus, ReportPriority, ReportCategory, ReportStatusHistory, ReportNote,
    Incident, Case, CaseNote, CaseStatusHistory, CaseStatus, CaseLevel, IncidentCategory,
)
from authentication.models import User


# =============================================================================
# INCIDENT / CASE SERIALIZERS (Step 2 - Case Lifecycle)
# =============================================================================

class IncidentSerializer(serializers.ModelSerializer):
    """Serializer for Incident model."""
    
    submitted_by_name = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    has_location = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Incident
        fields = [
            'id',
            'submitted_by',
            'submitted_by_name',
            'text_content',
            'category',
            'category_display',
            'latitude',
            'longitude',
            'area_name',
            'city',
            'state',
            'has_location',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_submitted_by_name(self, obj):
        return obj.submitted_by.identifier if obj.submitted_by else None


class CaseNoteSerializer(serializers.ModelSerializer):
    """Serializer for CaseNote model."""
    
    author_name = serializers.SerializerMethodField()
    # Flutter frontend expects 'content' field, but model uses 'note_text'
    content = serializers.CharField(source='note_text', read_only=True)
    
    class Meta:
        model = CaseNote
        fields = [
            'id',
            'case',
            'author',
            'author_name',
            'author_level',
            'note_text',
            'content',  # Alias for Flutter frontend
            'created_at',
        ]
        read_only_fields = fields
    
    def get_author_name(self, obj):
        return obj.author.identifier if obj.author else None


class CaseListSerializer(serializers.ModelSerializer):
    """Serializer for Case listing (lightweight)."""
    
    incident_text = serializers.CharField(source='incident.text_content', read_only=True)
    incident_category = serializers.CharField(source='incident.category', read_only=True)
    incident_category_display = serializers.CharField(source='incident.get_category_display', read_only=True)
    submitted_by = serializers.CharField(source='incident.submitted_by.identifier', read_only=True)
    submitted_at = serializers.DateTimeField(source='incident.created_at', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    current_level_display = serializers.CharField(source='get_current_level_display', read_only=True)
    is_sla_breached = serializers.SerializerMethodField()
    has_location = serializers.BooleanField(source='incident.has_location', read_only=True)
    latitude = serializers.DecimalField(source='incident.latitude', max_digits=10, decimal_places=7, read_only=True)
    longitude = serializers.DecimalField(source='incident.longitude', max_digits=10, decimal_places=7, read_only=True)
    area_name = serializers.CharField(source='incident.area_name', read_only=True, allow_null=True)
    city = serializers.CharField(source='incident.city', read_only=True, allow_null=True)
    state = serializers.CharField(source='incident.state', read_only=True, allow_null=True)
    
    # Media indicators for case list
    has_media = serializers.SerializerMethodField()
    media_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Case
        fields = [
            'id',
            'incident',
            'incident_text',
            'incident_category',
            'incident_category_display',
            'submitted_by',
            'submitted_at',
            'status',
            'status_display',
            'current_level',
            'current_level_display',
            'sla_deadline',
            'is_sla_breached',
            'has_location',
            'latitude',
            'longitude',
            'area_name',
            'city',
            'state',
            'has_media',
            'media_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_is_sla_breached(self, obj):
        if obj.status in [CaseStatus.SOLVED, CaseStatus.REJECTED]:
            return False
        return timezone.now() > obj.sla_deadline
    
    def get_has_media(self, obj):
        """Always safely return if incident has any media attachments (IncidentMedia)."""
        from .models import IncidentMedia
        try:
            return IncidentMedia.objects.filter(incident_id=obj.incident_id, is_deleted=False).exists()
        except Exception:
            return False

    def get_media_count(self, obj):
        """Always safely return count of media attachments for the incident (IncidentMedia)."""
        from .models import IncidentMedia
        try:
            return IncidentMedia.objects.filter(incident_id=obj.incident_id, is_deleted=False).count()
        except Exception:
            return 0


class CaseDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Case detail view (full info).
    
    Includes flat incident fields (incident_text, incident_category, etc.)
    for frontend compatibility, matching CaseListSerializer structure.
    Also includes nested incident object for complete data access.
    """
    
    # Flat incident fields (matching CaseListSerializer for frontend compatibility)
    incident_text = serializers.CharField(source='incident.text_content', read_only=True)
    incident_category = serializers.CharField(source='incident.category', read_only=True)
    incident_category_display = serializers.CharField(source='incident.get_category_display', read_only=True)
    submitted_by = serializers.CharField(source='incident.submitted_by.identifier', read_only=True)
    submitted_at = serializers.DateTimeField(source='incident.created_at', read_only=True)
    has_location = serializers.BooleanField(source='incident.has_location', read_only=True)
    latitude = serializers.DecimalField(source='incident.latitude', max_digits=10, decimal_places=7, read_only=True)
    longitude = serializers.DecimalField(source='incident.longitude', max_digits=10, decimal_places=7, read_only=True)
    area_name = serializers.CharField(source='incident.area_name', read_only=True, allow_null=True)
    city = serializers.CharField(source='incident.city', read_only=True, allow_null=True)
    state = serializers.CharField(source='incident.state', read_only=True, allow_null=True)
    
    # Nested objects for detailed views
    incident = IncidentSerializer(read_only=True)
    notes = CaseNoteSerializer(many=True, read_only=True)
    
    # Case status and level
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    current_level_display = serializers.CharField(source='get_current_level_display', read_only=True)
    is_sla_breached = serializers.SerializerMethodField()
    
    # Resolution info
    solved_by_name = serializers.SerializerMethodField()
    rejected_by_name = serializers.SerializerMethodField()
    
    # Media indicators
    has_media = serializers.SerializerMethodField()
    media_count = serializers.SerializerMethodField()
    media_files = serializers.SerializerMethodField()
    can_download_media = serializers.SerializerMethodField()
    
    class Meta:
        model = Case
        fields = [
            'id',
            # Flat incident fields (frontend compatibility)
            'incident_id',  # <-- Expose incident_id for frontend
            'incident_text',
            'incident_category',
            'incident_category_display',
            'submitted_by',
            'submitted_at',
            'has_location',
            'latitude',
            'longitude',
            'area_name',
            'city',
            'state',
            # Nested incident object (complete data)
            'incident',
            # Case status
            'status',
            'status_display',
            'current_level',
            'current_level_display',
            # SLA tracking
            'sla_deadline',
            'is_sla_breached',
            # Escalation info
            'escalation_count',
            'last_escalated_at',
            # Resolution info
            'solved_at',
            'solved_by',
            'solved_by_name',
            'solution_notes',
            'rejected_at',
            'rejected_by',
            'rejected_by_name',
            'rejection_reason',
            # Notes
            'notes',
            # Media
            'has_media',
            'media_count',
            'media_files',
            'can_download_media',
            # Timestamps
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_is_sla_breached(self, obj):
        if obj.status in [CaseStatus.SOLVED, CaseStatus.REJECTED]:
            return False
        return timezone.now() > obj.sla_deadline
    
    def get_solved_by_name(self, obj):
        return obj.solved_by.identifier if obj.solved_by else None
    
    def get_rejected_by_name(self, obj):
        return obj.rejected_by.identifier if obj.rejected_by else None
    
    def get_has_media(self, obj):
        """Check if incident has any media attachments."""
        from .models import IncidentMedia
        return IncidentMedia.objects.filter(
            incident_id=obj.incident_id,
            is_deleted=False
        ).exists()
    
    def get_media_count(self, obj):
        """Get count of media attachments for the incident."""
        from .models import IncidentMedia
        return IncidentMedia.objects.filter(
            incident_id=obj.incident_id,
            is_deleted=False
        ).count()
    
    def get_can_download_media(self, obj):
        """
        Check if current user can download media files.
        
        Rules:
        - Level-0 (Super Admin): CAN download
        - Level-1 (Senior Authority): CAN download
        - Level-2 Captain: CAN download
        - Level-2 (Field Authority): CANNOT download
        - JanMitra: NO access
        """
        from authentication.models import UserRole
        
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        user = request.user
        
        # JanMitra: NO access
        if user.is_janmitra:
            return False
        
        # Allowed roles for download
        allowed_roles = [
            UserRole.LEVEL_0,
            UserRole.LEVEL_1,
            UserRole.LEVEL_2_CAPTAIN,
        ]
        
        return user.role in allowed_roles
    
    def get_media_files(self, obj):
        """
        Get list of media files for the incident with role-based access flags.
        
        Each media file includes:
        - can_download: Whether current user can download this file
        - preview_url: URL for low-res preview (always available for authorities)
        - download_url: URL for full download (only if can_download)
        """
        from .models import IncidentMedia
        from authentication.models import UserRole
        
        request = self.context.get('request')
        can_download = False
        
        if request and request.user.is_authenticated:
            user = request.user
            if not user.is_janmitra:
                allowed_roles = [
                    UserRole.LEVEL_0,
                    UserRole.LEVEL_1,
                    UserRole.LEVEL_2_CAPTAIN,
                ]
                can_download = user.role in allowed_roles
        
        media_files = IncidentMedia.objects.filter(
            incident_id=obj.incident_id,
            is_deleted=False
        ).order_by('created_at')
        
        return [
            {
                'id': str(m.id),
                'media_type': m.media_type,
                'file_size': m.file_size,
                'content_type': m.content_type,
                'created_at': m.created_at.isoformat(),
                # Always provide preview URL for authorities
                'preview_url': f"/api/v1/incidents/media/{m.id}/preview/",
                # Download URL only for authorized roles
                'download_url': f"/api/v1/incidents/media/{m.id}/download/" if can_download else None,
                # Legacy field - use preview_url if can't download
                'url': f"/api/v1/incidents/media/{m.id}/download/" if can_download else f"/api/v1/incidents/media/{m.id}/preview/",
                'thumbnail_url': f"/api/v1/incidents/media/{m.id}/preview/",
                # Per-file download permission
                'can_download': can_download,
            }
            for m in media_files
        ]


class JanMitraCaseSerializer(serializers.ModelSerializer):
    """Serializer for JanMitra viewing their own cases (limited info)."""
    
    incident_text = serializers.CharField(source='incident.text_content', read_only=True)
    incident_category = serializers.CharField(source='incident.category', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Case
        fields = [
            'id',
            'incident_text',
            'incident_category',
            'status',
            'status_display',
            'created_at',
            'solved_at',
            'rejected_at',
        ]
        read_only_fields = fields


# =============================================================================
# LEGACY REPORT SERIALIZERS
# =============================================================================

class ReportCreateSerializer(serializers.Serializer):
    """
    Serializer for creating encrypted reports.
    
    All content fields are expected as base64-encoded strings
    and stored as binary data.
    """
    
    # Encrypted content (base64 encoded)
    encrypted_title = serializers.CharField(
        help_text="Base64-encoded encrypted title"
    )
    encrypted_content = serializers.CharField(
        help_text="Base64-encoded encrypted content"
    )
    encryption_iv = serializers.CharField(
        help_text="Base64-encoded initialization vector"
    )
    encryption_tag = serializers.CharField(
        help_text="Base64-encoded authentication tag"
    )
    encryption_key_id = serializers.CharField(
        max_length=64,
        help_text="Key identifier for key management"
    )
    
    # Metadata (not encrypted)
    category = serializers.ChoiceField(
        choices=ReportCategory.CHOICES,
        default=ReportCategory.GENERAL
    )
    priority = serializers.ChoiceField(
        choices=ReportPriority.CHOICES,
        default=ReportPriority.MEDIUM
    )
    jurisdiction_code = serializers.CharField(
        max_length=50,
        help_text="Jurisdiction code for routing"
    )
    location_zone = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True
    )
    incident_timestamp = serializers.DateTimeField(
        required=False,
        allow_null=True
    )
    submit_immediately = serializers.BooleanField(
        default=True,
        help_text="If true, submit immediately; if false, save as draft"
    )
    
    def validate_encrypted_title(self, value):
        """Validate and decode base64 title."""
        try:
            return base64.b64decode(value)
        except Exception:
            raise serializers.ValidationError("Invalid base64 encoding for title")
    
    def validate_encrypted_content(self, value):
        """Validate and decode base64 content."""
        try:
            return base64.b64decode(value)
        except Exception:
            raise serializers.ValidationError("Invalid base64 encoding for content")
    
    def validate_encryption_iv(self, value):
        """Validate and decode base64 IV."""
        try:
            decoded = base64.b64decode(value)
            if len(decoded) != 12 and len(decoded) != 16:
                raise serializers.ValidationError("IV must be 12 or 16 bytes")
            return decoded
        except Exception:
            raise serializers.ValidationError("Invalid base64 encoding for IV")
    
    def validate_encryption_tag(self, value):
        """Validate and decode base64 tag."""
        try:
            decoded = base64.b64decode(value)
            if len(decoded) != 16:
                raise serializers.ValidationError("Authentication tag must be 16 bytes")
            return decoded
        except Exception:
            raise serializers.ValidationError("Invalid base64 encoding for tag")
    
    def create(self, validated_data):
        user = self.context['request'].user
        
        # Generate report number
        report_number = Report.generate_report_number()
        
        # Get submitter trust score
        trust_score = 50
        if hasattr(user, 'janmitra_profile'):
            trust_score = user.janmitra_profile.trust_score
        
        # Create report
        report = Report.objects.create(
            report_number=report_number,
            submitted_by=user,
            encrypted_title=validated_data['encrypted_title'],
            encrypted_content=validated_data['encrypted_content'],
            encryption_iv=validated_data['encryption_iv'],
            encryption_tag=validated_data['encryption_tag'],
            encryption_key_id=validated_data['encryption_key_id'],
            category=validated_data.get('category', ReportCategory.GENERAL),
            priority=validated_data.get('priority', ReportPriority.MEDIUM),
            jurisdiction_code=validated_data['jurisdiction_code'],
            location_zone=validated_data.get('location_zone', ''),
            incident_timestamp=validated_data.get('incident_timestamp'),
            submitter_trust_score=trust_score,
            status=ReportStatus.DRAFT,
            created_by=user,
        )
        
        # Submit if requested
        if validated_data.get('submit_immediately', True):
            report.submit()
        
        # Update JanMitra report count
        if hasattr(user, 'janmitra_profile'):
            user.janmitra_profile.increment_report_count('submitted')
        
        return report


class JanMitraReportSerializer(serializers.ModelSerializer):
    """
    Serializer for JanMitra viewing their own reports.
    Limited information - no encrypted content exposed.
    """
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Report
        fields = [
            'id',
            'report_number',
            'status',
            'status_display',
            'category',
            'priority',
            'submitted_at',
            'created_at',
            'media_count',
        ]
        read_only_fields = fields


class ReportStatusSerializer(serializers.ModelSerializer):
    """
    Minimal status information for JanMitra.
    """
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Report
        fields = [
            'id',
            'report_number',
            'status',
            'status_display',
            'submitted_at',
            'updated_at',
        ]
        read_only_fields = fields


class ReportListSerializer(serializers.ModelSerializer):
    """
    Serializer for authority report listing.
    Shows metadata but not encrypted content.
    """
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    submitter_id = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = [
            'id',
            'report_number',
            'status',
            'status_display',
            'priority',
            'priority_display',
            'category',
            'category_display',
            'jurisdiction_code',
            'location_zone',
            'submitted_at',
            'incident_timestamp',
            'submitter_id',
            'submitter_trust_score',
            'assigned_to',
            'assigned_to_name',
            'is_escalated',
            'media_count',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_submitter_id(self, obj):
        """Return anonymized submitter ID."""
        return f"JM-{str(obj.submitted_by.id)[:8]}"
    
    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.identifier
        return None


class ReportDetailSerializer(serializers.ModelSerializer):
    """
    Detailed report serializer for authorities.
    
    Includes encrypted content as base64 for authorized access.
    Decryption status indicates if content can be decrypted.
    """
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    submitter_info = serializers.SerializerMethodField()
    encrypted_title_b64 = serializers.SerializerMethodField()
    encrypted_content_b64 = serializers.SerializerMethodField()
    encryption_iv_b64 = serializers.SerializerMethodField()
    encryption_tag_b64 = serializers.SerializerMethodField()
    status_history = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()
    can_decrypt = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = [
            'id',
            'report_number',
            'status',
            'status_display',
            'priority',
            'priority_display',
            'category',
            'category_display',
            'jurisdiction_code',
            'location_zone',
            'submitted_at',
            'incident_timestamp',
            'submitter_info',
            'submitter_trust_score',
            'assigned_to',
            'assigned_at',
            'is_escalated',
            'escalated_to',
            'escalated_at',
            'encrypted_title_b64',
            'encrypted_content_b64',
            'encryption_iv_b64',
            'encryption_tag_b64',
            'encryption_key_id',
            'decryption_authorized',
            'can_decrypt',
            'media_count',
            'resolution_notes',
            'closed_at',
            'status_history',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_submitter_info(self, obj):
        """Return submitter info based on identity reveal status."""
        request = self.context.get('request')
        
        info = {
            'anonymous_id': f"JM-{str(obj.submitted_by.id)[:8]}",
            'trust_score': obj.submitter_trust_score,
            'identity_revealed': False,
        }
        
        # Check if identity has been revealed
        if hasattr(obj.submitted_by, 'janmitra_profile'):
            profile = obj.submitted_by.janmitra_profile
            if profile.identity_revealed and request and request.user.is_level_1:
                info['identity_revealed'] = True
                info['user_id'] = str(obj.submitted_by.id)
        
        return info
    
    def get_encrypted_title_b64(self, obj):
        return base64.b64encode(obj.encrypted_title).decode('utf-8')
    
    def get_encrypted_content_b64(self, obj):
        return base64.b64encode(obj.encrypted_content).decode('utf-8')
    
    def get_encryption_iv_b64(self, obj):
        return base64.b64encode(obj.encryption_iv).decode('utf-8')
    
    def get_encryption_tag_b64(self, obj):
        return base64.b64encode(obj.encryption_tag).decode('utf-8')
    
    def get_status_history(self, obj):
        history = ReportStatusHistory.objects.filter(
            report=obj
        ).order_by('-created_at')[:10]
        
        return [
            {
                'from_status': h.from_status,
                'to_status': h.to_status,
                'changed_by': h.changed_by.identifier if not h.changed_by.is_anonymous else f"JM-{str(h.changed_by.id)[:8]}",
                'reason': h.reason,
                'timestamp': h.created_at.isoformat(),
            }
            for h in history
        ]
    
    def get_notes(self, obj):
        request = self.context.get('request')
        notes = ReportNote.objects.filter(report=obj)
        
        # Filter private notes based on user role
        if request and not request.user.is_level_1:
            notes = notes.filter(is_private=False)
        
        return [
            {
                'id': str(n.id),
                'author': n.author.identifier,
                'content': n.content,
                'is_private': n.is_private,
                'created_at': n.created_at.isoformat(),
            }
            for n in notes.order_by('-created_at')[:20]
        ]
    
    def get_can_decrypt(self, obj):
        """Check if current user can decrypt this report."""
        request = self.context.get('request')
        if not request:
            return False
        
        # Level 1 can always decrypt
        if request.user.is_level_1:
            return True
        
        # Others need explicit authorization
        return obj.decryption_authorized


class ReportValidateSerializer(serializers.Serializer):
    """Serializer for report validation."""
    
    notes = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="Validation notes"
    )


class ReportRejectSerializer(serializers.Serializer):
    """Serializer for report rejection."""
    
    reason = serializers.CharField(
        max_length=1000,
        help_text="Reason for rejection"
    )
    rejection_type = serializers.ChoiceField(
        choices=[
            ('invalid', 'Invalid'),
            ('duplicate', 'Duplicate'),
            ('rejected', 'Rejected'),
        ],
        default='rejected',
        help_text="Type of rejection"
    )


class ReportNoteSerializer(serializers.ModelSerializer):
    """Serializer for report notes."""
    
    author_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportNote
        fields = [
            'id',
            'content',
            'is_private',
            'author',
            'author_name',
            'created_at',
        ]
        read_only_fields = ['id', 'author', 'author_name', 'created_at']
    
    def get_author_name(self, obj):
        return obj.author.identifier


class CreateReportNoteSerializer(serializers.Serializer):
    """Serializer for creating report notes."""
    
    content = serializers.CharField(
        max_length=5000,
        help_text="Note content"
    )
    is_private = serializers.BooleanField(
        default=False,
        help_text="If true, only visible to same-level or higher authorities"
    )


# =============================================================================
# INCIDENT MEDIA SERIALIZERS
# =============================================================================

from .models import IncidentMedia, IncidentMediaType


class IncidentMediaSerializer(serializers.ModelSerializer):
    """
    Serializer for IncidentMedia - used for listing and detail views.
    
    NOTE: File URL is NOT included to prevent public access.
    Use the dedicated download endpoint instead.
    """
    
    media_type_display = serializers.CharField(source='get_media_type_display', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = IncidentMedia
        fields = [
            'id',
            'incident',
            'media_type',
            'media_type_display',
            'original_filename',
            'file_size',
            'content_type',
            'uploaded_by',
            'uploaded_by_name',
            'created_at',
        ]
        read_only_fields = ['id', 'incident', 'uploaded_by', 'created_at']
    
    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.identifier
        return None


class IncidentMediaUploadSerializer(serializers.Serializer):
    """
    Serializer for uploading media to an incident.
    
    Validates:
    - File type (photo/video only)
    - File size limits
    - Maximum files per incident (3)
    """
    
    file = serializers.FileField(
        help_text="Media file to upload (photo or video)"
    )
    
    def validate_file(self, value):
        """Validate uploaded file."""
        import os
        
        # Get file extension
        ext = os.path.splitext(value.name)[1].lower()
        
        # Determine media type from extension
        media_type = None
        for mtype, extensions in IncidentMediaType.ALLOWED_EXTENSIONS.items():
            if ext in extensions:
                media_type = mtype
                break
        
        if media_type is None:
            allowed_exts = []
            for exts in IncidentMediaType.ALLOWED_EXTENSIONS.values():
                allowed_exts.extend(exts)
            raise serializers.ValidationError(
                f"Invalid file type. Allowed: {', '.join(allowed_exts)}"
            )
        
        # Check file size
        max_size = IncidentMediaType.MAX_SIZES.get(media_type, 10 * 1024 * 1024)
        if value.size > max_size:
            max_mb = max_size / (1024 * 1024)
            raise serializers.ValidationError(
                f"File too large. Maximum size for {media_type}: {max_mb:.0f}MB"
            )
        
        # Validate content type if available
        if hasattr(value, 'content_type') and value.content_type:
            allowed_mimes = IncidentMediaType.ALLOWED_MIME_TYPES.get(media_type, [])
            if value.content_type not in allowed_mimes:
                raise serializers.ValidationError(
                    f"Invalid content type: {value.content_type}"
                )
        
        # Store detected media type for later use
        value.detected_media_type = media_type
        
        return value
    
    def validate(self, attrs):
        """Check if incident has reached max files limit."""
        incident = self.context.get('incident')
        if incident:
            current_count = IncidentMedia.get_count_for_incident(incident.id)
            if current_count >= IncidentMediaType.MAX_FILES_PER_INCIDENT:
                raise serializers.ValidationError({
                    'file': f"Maximum {IncidentMediaType.MAX_FILES_PER_INCIDENT} files allowed per incident."
                })
        return attrs
