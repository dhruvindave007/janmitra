"""
Audit models for JanMitra Backend.

Implements immutable, append-only audit logging for compliance.

Audit logs track:
- Authentication events (login, logout, token refresh)
- Report access events
- Escalation actions
- Decryption approvals
- Identity reveals
- User revocations
- All administrative actions

Design principles:
- Append-only: No updates or deletes allowed
- Immutable: Records cannot be modified
- Comprehensive: All sensitive actions logged
- Timestamped: Precise timing for forensics
"""

import uuid
from django.db import models
from django.utils import timezone


class AuditEventType:
    """
    Audit event type constants.
    Categorized by module for easier filtering.
    """
    
    # Authentication events
    AUTH_LOGIN_SUCCESS = 'auth.login.success'
    AUTH_LOGIN_FAILED = 'auth.login.failed'
    AUTH_LOGOUT = 'auth.logout'
    AUTH_TOKEN_REFRESH = 'auth.token.refresh'
    AUTH_TOKEN_REVOKED = 'auth.token.revoked'
    AUTH_PASSWORD_CHANGED = 'auth.password.changed'
    AUTH_DEVICE_REGISTERED = 'auth.device.registered'
    AUTH_DEVICE_INVALIDATED = 'auth.device.invalidated'
    
    # User management events
    USER_CREATED = 'user.created'
    USER_UPDATED = 'user.updated'
    USER_REVOKED = 'user.revoked'
    USER_SUSPENDED = 'user.suspended'
    USER_RESTORED = 'user.restored'
    
    # Invite code events
    INVITE_CREATED = 'invite.created'
    INVITE_USED = 'invite.used'
    INVITE_EXPIRED = 'invite.expired'
    
    # Report events
    REPORT_CREATED = 'report.created'
    REPORT_VIEWED = 'report.viewed'
    REPORT_ASSIGNED = 'report.assigned'
    REPORT_STATUS_CHANGED = 'report.status.changed'
    REPORT_VALIDATED = 'report.validated'
    REPORT_REJECTED = 'report.rejected'
    
    # Media events
    MEDIA_UPLOADED = 'media.uploaded'
    MEDIA_ACCESSED = 'media.accessed'
    MEDIA_DECRYPTED = 'media.decrypted'
    
    # Escalation events
    ESCALATION_CREATED = 'escalation.created'
    ESCALATION_APPROVED = 'escalation.approved'
    ESCALATION_REJECTED = 'escalation.rejected'
    
    # Identity reveal events (critical)
    IDENTITY_REVEAL_REQUESTED = 'identity.reveal.requested'
    IDENTITY_REVEAL_APPROVED = 'identity.reveal.approved'
    IDENTITY_REVEAL_REJECTED = 'identity.reveal.rejected'
    IDENTITY_REVEALED = 'identity.revealed'
    
    # Decryption events (critical)
    DECRYPTION_REQUESTED = 'decryption.requested'
    DECRYPTION_APPROVED = 'decryption.approved'
    DECRYPTION_REJECTED = 'decryption.rejected'
    DECRYPTION_PERFORMED = 'decryption.performed'
    
    # System events
    SYSTEM_ERROR = 'system.error'
    SYSTEM_SECURITY_ALERT = 'system.security.alert'
    
    # All choices for model field
    CHOICES = [
        # Authentication
        (AUTH_LOGIN_SUCCESS, 'Login Success'),
        (AUTH_LOGIN_FAILED, 'Login Failed'),
        (AUTH_LOGOUT, 'Logout'),
        (AUTH_TOKEN_REFRESH, 'Token Refresh'),
        (AUTH_TOKEN_REVOKED, 'Token Revoked'),
        (AUTH_PASSWORD_CHANGED, 'Password Changed'),
        (AUTH_DEVICE_REGISTERED, 'Device Registered'),
        (AUTH_DEVICE_INVALIDATED, 'Device Invalidated'),
        
        # User Management
        (USER_CREATED, 'User Created'),
        (USER_UPDATED, 'User Updated'),
        (USER_REVOKED, 'User Revoked'),
        (USER_SUSPENDED, 'User Suspended'),
        (USER_RESTORED, 'User Restored'),
        
        # Invite Codes
        (INVITE_CREATED, 'Invite Created'),
        (INVITE_USED, 'Invite Used'),
        (INVITE_EXPIRED, 'Invite Expired'),
        
        # Reports
        (REPORT_CREATED, 'Report Created'),
        (REPORT_VIEWED, 'Report Viewed'),
        (REPORT_ASSIGNED, 'Report Assigned'),
        (REPORT_STATUS_CHANGED, 'Report Status Changed'),
        (REPORT_VALIDATED, 'Report Validated'),
        (REPORT_REJECTED, 'Report Rejected'),
        
        # Media
        (MEDIA_UPLOADED, 'Media Uploaded'),
        (MEDIA_ACCESSED, 'Media Accessed'),
        (MEDIA_DECRYPTED, 'Media Decrypted'),
        
        # Escalation
        (ESCALATION_CREATED, 'Escalation Created'),
        (ESCALATION_APPROVED, 'Escalation Approved'),
        (ESCALATION_REJECTED, 'Escalation Rejected'),
        
        # Identity Reveal
        (IDENTITY_REVEAL_REQUESTED, 'Identity Reveal Requested'),
        (IDENTITY_REVEAL_APPROVED, 'Identity Reveal Approved'),
        (IDENTITY_REVEAL_REJECTED, 'Identity Reveal Rejected'),
        (IDENTITY_REVEALED, 'Identity Revealed'),
        
        # Decryption
        (DECRYPTION_REQUESTED, 'Decryption Requested'),
        (DECRYPTION_APPROVED, 'Decryption Approved'),
        (DECRYPTION_REJECTED, 'Decryption Rejected'),
        (DECRYPTION_PERFORMED, 'Decryption Performed'),
        
        # System
        (SYSTEM_ERROR, 'System Error'),
        (SYSTEM_SECURITY_ALERT, 'Security Alert'),
    ]


class AuditSeverity:
    """Severity levels for audit events."""
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'
    
    CHOICES = [
        (DEBUG, 'Debug'),
        (INFO, 'Info'),
        (WARNING, 'Warning'),
        (ERROR, 'Error'),
        (CRITICAL, 'Critical'),
    ]


class AuditLogManager(models.Manager):
    """
    Custom manager for AuditLog.
    Prevents any modifications to existing records.
    """
    
    def update(self, *args, **kwargs):
        """Prevent bulk updates on audit logs."""
        raise PermissionError("Audit logs are immutable and cannot be updated.")
    
    def delete(self, *args, **kwargs):
        """Prevent bulk deletes on audit logs."""
        raise PermissionError("Audit logs are immutable and cannot be deleted.")


class AuditLog(models.Model):
    """
    Immutable audit log for all sensitive actions.
    
    Design principles:
    - UUID primary key
    - No foreign keys (stores IDs as strings for immutability)
    - No update/delete operations allowed
    - Comprehensive metadata capture
    
    Security note: This model intentionally does not inherit from BaseModel
    because audit logs must never be soft-deleted or modified.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Event identification
    event_type = models.CharField(
        max_length=50,
        choices=AuditEventType.CHOICES,
        db_index=True,
        help_text="Type of event being logged"
    )
    
    severity = models.CharField(
        max_length=10,
        choices=AuditSeverity.CHOICES,
        default=AuditSeverity.INFO,
        db_index=True,
        help_text="Severity level of the event"
    )
    
    # Timestamp (immutable after creation)
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the event occurred"
    )
    
    # Actor information (who performed the action)
    actor_id = models.CharField(
        max_length=36,
        blank=True,
        db_index=True,
        help_text="UUID of user who performed action (as string for immutability)"
    )
    
    actor_role = models.CharField(
        max_length=20,
        blank=True,
        help_text="Role of actor at time of action"
    )
    
    actor_identifier = models.CharField(
        max_length=255,
        blank=True,
        help_text="Identifier of actor (anonymized for JanMitra)"
    )
    
    # Target information (what was acted upon)
    target_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of entity being acted upon"
    )
    
    target_id = models.CharField(
        max_length=36,
        blank=True,
        db_index=True,
        help_text="UUID of target entity (as string)"
    )
    
    # Request context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address"
    )
    
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        help_text="Client user agent string"
    )
    
    device_fingerprint_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="Hashed device fingerprint"
    )
    
    # API context
    request_method = models.CharField(
        max_length=10,
        blank=True,
        help_text="HTTP method"
    )
    
    request_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="API endpoint path"
    )
    
    # Event details
    description = models.TextField(
        blank=True,
        help_text="Human-readable description of event"
    )
    
    # Structured metadata (JSON)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional structured data about the event"
    )
    
    # Outcome
    success = models.BooleanField(
        default=True,
        help_text="Whether the action was successful"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if action failed"
    )
    
    # Custom manager to prevent modifications
    objects = AuditLogManager()
    
    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['actor_id', 'timestamp']),
            models.Index(fields=['target_id', 'timestamp']),
            models.Index(fields=['severity', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.timestamp} | {self.event_type} | {self.actor_identifier or 'system'}"
    
    def save(self, *args, **kwargs):
        """
        Override save to enforce append-only behavior.
        Only allows creation, not updates.
        """
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise PermissionError("Audit logs are immutable and cannot be updated.")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion of audit logs."""
        raise PermissionError("Audit logs are immutable and cannot be deleted.")
    
    @classmethod
    def log(cls, event_type, actor=None, target=None, request=None, 
            success=True, description='', metadata=None, severity=None):
        """
        Create an audit log entry.
        
        Args:
            event_type: One of AuditEventType constants
            actor: User performing the action (or None for system)
            target: Object being acted upon (optional)
            request: Django request object for context
            success: Whether action succeeded
            description: Human-readable description
            metadata: Additional structured data
            severity: Severity level (auto-determined if not provided)
        """
        # Determine severity if not provided
        if severity is None:
            if not success:
                severity = AuditSeverity.ERROR
            elif 'identity' in event_type or 'decryption' in event_type:
                severity = AuditSeverity.CRITICAL
            elif 'revoked' in event_type or 'failed' in event_type:
                severity = AuditSeverity.WARNING
            else:
                severity = AuditSeverity.INFO
        
        # Extract actor information
        actor_id = ''
        actor_role = ''
        actor_identifier = ''
        
        if actor:
            actor_id = str(actor.id)
            actor_role = actor.role
            # Anonymize JanMitra identifier in logs
            if actor.is_anonymous:
                actor_identifier = f"JanMitra-{str(actor.id)[:8]}"
            else:
                actor_identifier = actor.identifier
        
        # Extract target information
        target_type = ''
        target_id = ''
        
        if target:
            target_type = target.__class__.__name__
            target_id = str(target.id) if hasattr(target, 'id') else str(target.pk)
        
        # Extract request context
        ip_address = None
        user_agent = ''
        request_method = ''
        request_path = ''
        device_fingerprint_hash = ''
        
        if request:
            ip_address = cls._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            request_method = request.method
            request_path = request.path[:500]
            device_fingerprint_hash = request.META.get('HTTP_X_DEVICE_FINGERPRINT', '')
        
        return cls.objects.create(
            event_type=event_type,
            severity=severity,
            actor_id=actor_id,
            actor_role=actor_role,
            actor_identifier=actor_identifier,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint_hash=device_fingerprint_hash,
            request_method=request_method,
            request_path=request_path,
            description=description,
            metadata=metadata or {},
            success=success,
        )
    
    @staticmethod
    def _get_client_ip(request):
        """Extract client IP from request, handling proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class IdentityRevealLog(models.Model):
    """
    Special audit log for identity reveal events.
    
    This is a separate, extra-protected log specifically for 
    tracking when JanMitra identities are revealed.
    
    Compliance requirement: Must retain for minimum 7 years.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True
    )
    
    # The JanMitra whose identity was revealed
    janmitra_user_id = models.CharField(
        max_length=36,
        db_index=True,
        help_text="UUID of JanMitra user whose identity was revealed"
    )
    
    # The authority who received the revealed identity
    revealed_to_user_id = models.CharField(
        max_length=36,
        db_index=True,
        help_text="UUID of authority who received the identity"
    )
    
    revealed_to_role = models.CharField(
        max_length=20,
        help_text="Role of authority at time of reveal"
    )
    
    # The authority who approved the reveal
    approved_by_user_id = models.CharField(
        max_length=36,
        db_index=True,
        help_text="UUID of Level 1 authority who approved"
    )
    
    # Related report (if applicable)
    related_report_id = models.CharField(
        max_length=36,
        blank=True,
        help_text="UUID of related report"
    )
    
    # Justification
    justification = models.TextField(
        help_text="Legal/operational justification for reveal"
    )
    
    # Legal reference
    legal_authority = models.CharField(
        max_length=200,
        blank=True,
        help_text="Legal authority/section under which reveal was authorized"
    )
    
    # Request context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'identity_reveal_logs'
        verbose_name = 'Identity Reveal Log'
        verbose_name_plural = 'Identity Reveal Logs'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Identity reveal: {self.janmitra_user_id[:8]} to {self.revealed_to_user_id[:8]} at {self.timestamp}"
    
    def save(self, *args, **kwargs):
        """Enforce append-only behavior."""
        if self.pk and IdentityRevealLog.objects.filter(pk=self.pk).exists():
            raise PermissionError("Identity reveal logs are immutable.")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion."""
        raise PermissionError("Identity reveal logs cannot be deleted.")
