"""
Escalation models for JanMitra Backend.

Contains:
- Escalation: Report escalation requests from Level 2 to Level 1
- IdentityRevealRequest: Requests to reveal JanMitra identity
- DecryptionRequest: Requests for lawful access decryption

Workflow:
1. Level 2 can escalate reports to Level 1
2. Level 1 can approve/reject escalations
3. Level 1 can authorize identity reveals and decryption

All actions are fully audited.
"""

from django.db import models
from django.utils import timezone

from core.models import BaseModel, AuditableModel


class EscalationStatus:
    """Escalation request status constants."""
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    WITHDRAWN = 'withdrawn'
    
    CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (WITHDRAWN, 'Withdrawn'),
    ]


class EscalationPriority:
    """Escalation urgency levels."""
    ROUTINE = 'routine'
    PRIORITY = 'priority'
    URGENT = 'urgent'
    IMMEDIATE = 'immediate'
    
    CHOICES = [
        (ROUTINE, 'Routine'),
        (PRIORITY, 'Priority'),
        (URGENT, 'Urgent'),
        (IMMEDIATE, 'Immediate'),
    ]


class Escalation(AuditableModel):
    """
    Report escalation from Level 2 to Level 1.
    
    Workflow:
    1. Level 2 creates escalation request for a report
    2. Level 1 receives notification
    3. Level 1 reviews and approves/rejects
    4. If approved, report is assigned to Level 1
    """
    
    # The report being escalated
    report = models.ForeignKey(
        'reports.Report',
        on_delete=models.CASCADE,
        related_name='escalations',
        help_text="Report being escalated"
    )
    
    # Who is escalating (Level 2)
    escalated_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='escalations_created',
        help_text="Level 2 authority creating escalation"
    )
    
    # Target authority (Level 1)
    escalated_to = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='escalations_received',
        help_text="Level 1 authority to handle escalation"
    )
    
    # Request details
    priority = models.CharField(
        max_length=20,
        choices=EscalationPriority.CHOICES,
        default=EscalationPriority.ROUTINE,
        help_text="Escalation urgency"
    )
    
    reason = models.TextField(
        help_text="Reason for escalation"
    )
    
    additional_notes = models.TextField(
        blank=True,
        help_text="Additional context or notes"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=EscalationStatus.CHOICES,
        default=EscalationStatus.PENDING,
        db_index=True,
        help_text="Current escalation status"
    )
    
    # Resolution
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When escalation was resolved"
    )
    
    resolved_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='escalations_resolved',
        help_text="Authority who resolved the escalation"
    )
    
    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes on resolution"
    )
    
    class Meta:
        db_table = 'escalations'
        verbose_name = 'Escalation'
        verbose_name_plural = 'Escalations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['escalated_to', 'status']),
        ]
    
    def __str__(self):
        return f"Escalation for {self.report.report_number} ({self.status})"
    
    def approve(self, approved_by, notes=''):
        """Approve the escalation."""
        if self.status != EscalationStatus.PENDING:
            raise ValueError("Can only approve pending escalations")
        
        self.status = EscalationStatus.APPROVED
        self.resolved_at = timezone.now()
        self.resolved_by = approved_by
        self.resolution_notes = notes
        self.save()
        
        # Update the report
        self.report.escalate(self.escalated_to, self.escalated_by)
    
    def reject(self, rejected_by, notes=''):
        """Reject the escalation."""
        if self.status != EscalationStatus.PENDING:
            raise ValueError("Can only reject pending escalations")
        
        self.status = EscalationStatus.REJECTED
        self.resolved_at = timezone.now()
        self.resolved_by = rejected_by
        self.resolution_notes = notes
        self.save()
    
    def withdraw(self, withdrawn_by, notes=''):
        """Withdraw the escalation (by original requester)."""
        if self.status != EscalationStatus.PENDING:
            raise ValueError("Can only withdraw pending escalations")
        
        self.status = EscalationStatus.WITHDRAWN
        self.resolved_at = timezone.now()
        self.resolved_by = withdrawn_by
        self.resolution_notes = notes
        self.save()


class IdentityRevealRequest(AuditableModel):
    """
    Request to reveal a JanMitra member's identity.
    
    This is a CRITICAL security operation:
    - Can only be requested by authorities
    - Must be approved by Level 1
    - Requires legal justification
    - Fully audited in special log
    
    Identity reveal is irreversible for the specific report context.
    """
    
    # The JanMitra member whose identity is being requested
    target_user = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='identity_reveal_requests',
        help_text="JanMitra member whose identity is requested"
    )
    
    # Related report (if applicable)
    related_report = models.ForeignKey(
        'reports.Report',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='identity_reveal_requests',
        help_text="Related report if applicable"
    )
    
    # Requester
    requested_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='identity_reveals_requested',
        help_text="Authority requesting identity reveal"
    )
    
    # Legal/operational justification (required)
    justification = models.TextField(
        help_text="Legal and operational justification for reveal"
    )
    
    legal_authority = models.CharField(
        max_length=200,
        help_text="Legal authority/section under which reveal is requested"
    )
    
    case_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Case/FIR/investigation reference number"
    )
    
    urgency = models.CharField(
        max_length=20,
        choices=EscalationPriority.CHOICES,
        default=EscalationPriority.ROUTINE,
        help_text="Urgency of the request"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=EscalationStatus.CHOICES,
        default=EscalationStatus.PENDING,
        db_index=True,
        help_text="Request status"
    )
    
    # Approval (Level 1 only)
    reviewed_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='identity_reveals_reviewed',
        help_text="Level 1 authority who reviewed"
    )
    
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When request was reviewed"
    )
    
    review_notes = models.TextField(
        blank=True,
        help_text="Notes from reviewer"
    )
    
    # If approved, when identity was actually revealed
    revealed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When identity was actually revealed"
    )
    
    # Validity period (optional, for time-limited access)
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiry for identity access"
    )
    
    class Meta:
        db_table = 'identity_reveal_requests'
        verbose_name = 'Identity Reveal Request'
        verbose_name_plural = 'Identity Reveal Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'urgency']),
            models.Index(fields=['target_user', 'status']),
        ]
    
    def __str__(self):
        return f"Identity reveal request for {self.target_user} ({self.status})"
    
    def approve(self, approved_by, notes=''):
        """
        Approve identity reveal request.
        Can only be done by Level 1.
        """
        if not approved_by.is_level_1:
            raise PermissionError("Only Level 1 can approve identity reveals")
        
        if self.status != EscalationStatus.PENDING:
            raise ValueError("Can only approve pending requests")
        
        self.status = EscalationStatus.APPROVED
        self.reviewed_by = approved_by
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
    
    def reject(self, rejected_by, notes=''):
        """Reject identity reveal request."""
        if not rejected_by.is_level_1:
            raise PermissionError("Only Level 1 can reject identity reveals")
        
        if self.status != EscalationStatus.PENDING:
            raise ValueError("Can only reject pending requests")
        
        self.status = EscalationStatus.REJECTED
        self.reviewed_by = rejected_by
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
    
    def execute_reveal(self, executor):
        """
        Actually reveal the identity.
        Must be approved first.
        """
        if self.status != EscalationStatus.APPROVED:
            raise PermissionError("Request must be approved before reveal")
        
        # Update JanMitra profile
        profile = self.target_user.janmitra_profile
        profile.identity_revealed = True
        profile.identity_revealed_at = timezone.now()
        profile.identity_revealed_to = executor
        profile.save()
        
        self.revealed_at = timezone.now()
        self.save()
        
        # Create immutable identity reveal log
        from audit.models import IdentityRevealLog
        IdentityRevealLog.objects.create(
            janmitra_user_id=str(self.target_user.id),
            revealed_to_user_id=str(self.requested_by.id),
            revealed_to_role=self.requested_by.role,
            approved_by_user_id=str(self.reviewed_by.id),
            related_report_id=str(self.related_report.id) if self.related_report else '',
            justification=self.justification,
            legal_authority=self.legal_authority,
        )


class DecryptionRequest(AuditableModel):
    """
    Request for lawful decryption of report content.
    
    Security design:
    - Reports are encrypted client-side
    - Normal access shows only encrypted content
    - Level 1 can authorize decryption for lawful access
    - Decryption key is released only after approval
    
    This provides controlled lawful access while protecting
    privacy by default.
    """
    
    # The report to decrypt
    report = models.ForeignKey(
        'reports.Report',
        on_delete=models.PROTECT,
        related_name='decryption_requests',
        help_text="Report to decrypt"
    )
    
    # Requester
    requested_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        related_name='decryption_requests_created',
        help_text="Authority requesting decryption"
    )
    
    # Justification
    reason = models.TextField(
        help_text="Reason for decryption request"
    )
    
    legal_authority = models.CharField(
        max_length=200,
        blank=True,
        help_text="Legal authority for decryption"
    )
    
    case_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Case/investigation reference"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=EscalationStatus.CHOICES,
        default=EscalationStatus.PENDING,
        db_index=True
    )
    
    # Review
    reviewed_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='decryption_requests_reviewed'
    )
    
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    review_notes = models.TextField(
        blank=True
    )
    
    # Decryption scope
    include_media = models.BooleanField(
        default=False,
        help_text="Whether to also decrypt attached media"
    )
    
    class Meta:
        db_table = 'decryption_requests'
        verbose_name = 'Decryption Request'
        verbose_name_plural = 'Decryption Requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Decryption request for {self.report.report_number} ({self.status})"
    
    def approve(self, approved_by, notes=''):
        """Approve decryption request."""
        if not approved_by.is_level_1:
            raise PermissionError("Only Level 1 can approve decryption")
        
        if self.status != EscalationStatus.PENDING:
            raise ValueError("Can only approve pending requests")
        
        self.status = EscalationStatus.APPROVED
        self.reviewed_by = approved_by
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
        
        # Update report
        self.report.authorize_decryption(approved_by, notes)
    
    def reject(self, rejected_by, notes=''):
        """Reject decryption request."""
        if not rejected_by.is_level_1:
            raise PermissionError("Only Level 1 can reject decryption")
        
        if self.status != EscalationStatus.PENDING:
            raise ValueError("Can only reject pending requests")
        
        self.status = EscalationStatus.REJECTED
        self.reviewed_by = rejected_by
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
