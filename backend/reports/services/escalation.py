"""
EscalationService: SLA breach detection and auto-escalation.

Handles:
- Checking for SLA breaches
- Auto-escalating cases (L0/L1/L2 → L3, L3 → L4)
- Resetting SLA deadlines after escalation
- Logging escalations in EscalationHistory
- Adding system messages for escalation events

Usage:
    from reports.services import EscalationService
    
    # Check and escalate breached cases
    escalated = EscalationService.process_sla_breaches()
    
    # Manual escalation
    EscalationService.escalate_case(case, escalated_by=user, reason="...")
"""

from datetime import timedelta
from typing import List, Optional, Tuple

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from authentication.models import User, UserRole
from reports.models import (
    Case, CaseStatus, CaseLevel, CaseStatusHistory,
    EscalationHistory, EscalationType, EventType
)


class EscalationError(Exception):
    """Base exception for escalation errors."""
    pass


class CannotEscalateError(EscalationError):
    """Raised when case cannot be escalated."""
    pass


class EscalationService:
    """
    Service for managing case escalations.
    
    SLA Rules (per .ai architecture):
    - L0/L1/L2 (station level): 48h SLA, escalate to L3
    - L3: 48h SLA, escalate to L4
    - L4: No SLA (final level)
    
    Escalation flow:
    1. Check if case's SLA deadline has passed
    2. If yes and case is still active, escalate to next level
    3. Reset SLA deadline (another 48h at new level)
    4. Update status to ESCALATED
    5. Log in EscalationHistory
    6. Add system message
    """
    
    # SLA duration in hours
    SLA_HOURS = 48
    
    # Escalation paths
    ESCALATION_MAP = {
        'L0': 'L3',  # Station level → Higher authority
        'L1': 'L3',
        'L2': 'L3',
        'L3': 'L4',  # Higher → Top
        # L4 has no escalation (final level)
    }
    
    # Levels that have SLA (L4 does not)
    SLA_LEVELS = ['L0', 'L1', 'L2', 'L3']
    
    # Statuses that can be escalated (not terminal, not already escalated beyond station)
    ESCALATABLE_STATUSES = [
        CaseStatus.NEW,
        CaseStatus.ASSIGNED,
        CaseStatus.IN_PROGRESS,
        CaseStatus.ESCALATED,  # Can be escalated further (L3 → L4)
        CaseStatus.OPEN,  # Legacy
    ]
    
    @classmethod
    def check_sla_breach(cls, case: Case) -> bool:
        """
        Check if a case has breached its SLA.
        
        Args:
            case: Case to check
            
        Returns:
            True if SLA is breached, False otherwise
        """
        if case.status in CaseStatus.TERMINAL_STATES:
            return False
        
        if case.current_level not in cls.SLA_LEVELS:
            return False  # L4 has no SLA
        
        if not case.sla_deadline:
            return False
        
        now = timezone.now()
        return now > case.sla_deadline
    
    @classmethod
    def get_breached_cases(cls) -> List[Case]:
        """
        Get all cases that have breached SLA and need escalation.
        
        Returns:
            List of Case objects that need escalation
        """
        now = timezone.now()
        
        return list(
            Case.objects.filter(
                status__in=cls.ESCALATABLE_STATUSES,
                current_level__in=cls.SLA_LEVELS,
                sla_deadline__lt=now,
                is_deleted=False
            ).select_for_update().select_related('police_station', 'assigned_officer')
        )
    
    @classmethod
    def process_sla_breaches(cls) -> List[Tuple[Case, str, str]]:
        """
        Process all SLA breaches: mark breached and escalate.
        
        This is the main entry point for the escalation cron job.
        
        Returns:
            List of tuples (case, from_level, to_level) for escalated cases
        """
        escalated = []
        
        with transaction.atomic():
            breached_cases = cls.get_breached_cases()
            
            for case in breached_cases:
                try:
                    from_level, to_level = cls._auto_escalate(case)
                    escalated.append((case, from_level, to_level))
                except CannotEscalateError:
                    # Log but continue with other cases
                    pass
        
        # Send notifications outside transaction
        for case, from_level, to_level in escalated:
            try:
                from notifications.services import NotificationService
                NotificationService.notify_case_escalated(case, from_level, to_level)
            except Exception:
                pass  # Don't fail escalation if notification fails
        
        return escalated
    
    @classmethod
    def escalate_case(
        cls,
        case: Case,
        escalated_by: Optional[User] = None,
        reason: str = ''
    ) -> Tuple[str, str]:
        """
        Manually escalate a case to the next level.
        
        Args:
            case: Case to escalate
            escalated_by: User requesting escalation (None for auto)
            reason: Reason for escalation
            
        Returns:
            Tuple of (from_level, to_level)
            
        Raises:
            CannotEscalateError: If case cannot be escalated
        """
        from_level = case.current_level
        to_level = cls.ESCALATION_MAP.get(from_level)
        
        if not to_level:
            raise CannotEscalateError(
                f"Case at level {from_level} cannot be escalated further"
            )
        
        # Validate case can be escalated
        cls._validate_can_escalate(case)
        
        escalation_type = EscalationType.MANUAL if escalated_by else EscalationType.AUTO
        default_reason = reason or cls._default_reason(escalation_type, from_level, to_level)
        
        with transaction.atomic():
            # Lock case for update
            locked_case = Case.objects.select_for_update().get(id=case.id)
            
            now = timezone.now()
            old_status = locked_case.status
            
            # Mark SLA breach if this is first breach
            if locked_case.sla_breached_at is None:
                locked_case.sla_breached_at = now
            
            # Update case level and status
            locked_case.current_level = to_level
            locked_case.status = CaseStatus.ESCALATED
            locked_case.last_escalated_at = now
            locked_case.escalation_count = (locked_case.escalation_count or 0) + 1
            
            # Reset SLA deadline if new level has SLA
            if to_level in cls.SLA_LEVELS:
                locked_case.sla_deadline = now + timedelta(hours=cls.SLA_HOURS)
            
            locked_case.save(update_fields=[
                'current_level',
                'status',
                'sla_breached_at',
                'sla_deadline',
                'last_escalated_at',
                'escalation_count',
                'updated_at'
            ])
            
            # Log status change
            CaseStatusHistory.objects.create(
                case=locked_case,
                from_status=old_status,
                to_status=CaseStatus.ESCALATED,
                from_level=from_level,
                to_level=to_level,
                changed_by=escalated_by,
                reason=default_reason,
                is_auto_escalation=(escalation_type == EscalationType.AUTO),
            )
            
            # Log escalation
            EscalationHistory.objects.create(
                case=locked_case,
                event_type=EventType.ESCALATION,
                from_level=from_level,
                to_level=to_level,
                escalation_type=escalation_type,
                escalated_by=escalated_by,
                assigned_officer=None,
                reason=default_reason
            )
            
            # Add system message
            from reports.services.investigation import InvestigationService
            if escalation_type == EscalationType.AUTO:
                msg = f"Case auto-escalated from {from_level} to {to_level} due to SLA breach."
            else:
                by_str = escalated_by.identifier if escalated_by else "system"
                msg = f"Case escalated from {from_level} to {to_level} by {by_str}."
            InvestigationService.send_system_message(case=locked_case, text=msg)
        
        # Send notification outside transaction
        try:
            from notifications.services import NotificationService
            NotificationService.notify_case_escalated_new(
                case=case,
                from_level=from_level,
                to_level=to_level,
                escalated_by=escalated_by,
                reason=reason
            )
        except Exception:
            pass  # Don't fail escalation if notification fails
        
        return from_level, to_level
    
    @classmethod
    def _auto_escalate(cls, case: Case) -> Tuple[str, str]:
        """
        Auto-escalate a case due to SLA breach.
        
        Internal method called by process_sla_breaches.
        
        Args:
            case: Case to escalate
            
        Returns:
            Tuple of (from_level, to_level)
        """
        return cls.escalate_case(
            case,
            escalated_by=None,
            reason="Automatic escalation due to SLA breach"
        )
    
    @classmethod
    def get_escalation_history(cls, case: Case) -> List[EscalationHistory]:
        """
        Get escalation history for a case.
        
        Args:
            case: Case to get history for
            
        Returns:
            List of EscalationHistory records, newest first
        """
        return list(
            EscalationHistory.objects.filter(
                case=case,
                event_type=EventType.ESCALATION,
                is_deleted=False
            ).select_related('escalated_by').order_by('-created_at')
        )
    
    @classmethod
    def get_sla_status(cls, case: Case) -> dict:
        """
        Get SLA status for a case.
        
        Args:
            case: Case to check
            
        Returns:
            Dict with SLA status information
        """
        now = timezone.now()
        
        if case.current_level not in cls.SLA_LEVELS:
            return {
                'has_sla': False,
                'level': case.current_level,
                'message': 'No SLA at this level (L4 is final)'
            }
        
        if not case.sla_deadline:
            return {
                'has_sla': True,
                'level': case.current_level,
                'deadline': None,
                'message': 'SLA deadline not set'
            }
        
        time_remaining = case.sla_deadline - now
        is_breached = time_remaining.total_seconds() < 0
        
        if is_breached:
            breach_duration = now - case.sla_deadline
            return {
                'has_sla': True,
                'is_breached': True,
                'breached_at': case.sla_breached_at,
                'deadline': case.sla_deadline,
                'breach_duration_hours': round(breach_duration.total_seconds() / 3600, 1),
                'can_escalate': case.current_level in cls.ESCALATION_MAP,
                'next_level': cls.ESCALATION_MAP.get(case.current_level)
            }
        
        hours_remaining = time_remaining.total_seconds() / 3600
        return {
            'has_sla': True,
            'is_breached': False,
            'deadline': case.sla_deadline,
            'hours_remaining': round(hours_remaining, 1),
            'is_warning': hours_remaining <= 4,  # Warning at 4 hours
        }
    
    @classmethod
    def get_cases_needing_warning(cls, hours_threshold: int = 4) -> List[Case]:
        """
        Get cases approaching SLA deadline (for warning notifications).
        
        Args:
            hours_threshold: Hours before deadline to trigger warning
            
        Returns:
            List of cases within warning threshold
        """
        now = timezone.now()
        warning_threshold = now + timedelta(hours=hours_threshold)
        
        return list(
            Case.objects.filter(
                status__in=cls.ESCALATABLE_STATUSES,
                current_level__in=cls.SLA_LEVELS,
                sla_deadline__gt=now,
                sla_deadline__lte=warning_threshold,
                is_deleted=False
            ).select_related('police_station', 'assigned_officer')
        )
    
    @classmethod
    def calculate_new_sla_deadline(cls, from_time: Optional = None) -> timezone.datetime:
        """
        Calculate a new SLA deadline.
        
        Args:
            from_time: Start time (default: now)
            
        Returns:
            DateTime of SLA deadline
        """
        start = from_time or timezone.now()
        return start + timedelta(hours=cls.SLA_HOURS)
    
    @classmethod
    def _validate_can_escalate(cls, case: Case) -> None:
        """
        Validate that a case can be escalated.
        
        Args:
            case: Case to validate
            
        Raises:
            CannotEscalateError: If case cannot be escalated
        """
        if case.status in CaseStatus.TERMINAL_STATES:
            raise CannotEscalateError(
                f"Cannot escalate {case.status} cases. Case is in terminal state."
            )
        
        if case.current_level not in cls.ESCALATION_MAP:
            raise CannotEscalateError(
                f"Case at level {case.current_level} cannot be escalated further"
            )
    
    @classmethod
    def _default_reason(cls, escalation_type: str, from_level: str, to_level: str) -> str:
        """Generate default escalation reason."""
        if escalation_type == EscalationType.AUTO:
            return f"Automatic escalation from {from_level} to {to_level} due to SLA breach"
        return f"Manual escalation from {from_level} to {to_level}"
