"""
AssignmentService: L1 assigns L0 officer to cases.

Rules per .ai architecture:
- Only L1 assigns L0
- Only one L0 per case (assign overwrites existing)
- L0 must belong to same police station as case
- Use select_for_update when modifying Case
- Use transaction.atomic for multi-step operations
- Add system message for assignment
- Notify assigned L0 officer

Usage:
    from reports.services import AssignmentService
    
    # Assign officer to case (overwrites existing assignment)
    case = AssignmentService.assign_officer(
        case=case,
        officer=l0_officer,
        assigned_by=l1_user
    )
"""

from typing import List

from django.db import transaction
from django.utils import timezone

from authentication.models import User, UserRole
from reports.models import Case, EscalationHistory, EventType, CaseStatus, CaseStatusHistory


class AssignmentError(Exception):
    """Base exception for assignment errors."""
    pass


class InvalidOfficerError(AssignmentError):
    """Raised when officer is not valid for assignment."""
    pass


class InvalidAssignerError(AssignmentError):
    """Raised when user is not authorized to make assignments."""
    pass


class CaseNotAssignableError(AssignmentError):
    """Raised when case cannot be assigned (wrong status/state)."""
    pass


class AssignmentService:
    """
    Service for managing officer assignments to cases.
    
    Rules (per .ai architecture):
    - Only L1 (PSO) can assign officers
    - Only L0 officers can be assigned
    - Officer must be from the same station as the case
    - Only one L0 per case (assign overwrites existing)
    - Case must be at station level (not escalated beyond L2)
    - Use select_for_update when modifying Case
    - Add system message for assignment events
    - Notify assigned officer
    """
    
    @classmethod
    def assign_officer(
        cls,
        case: Case,
        officer: User,
        assigned_by: User,
        notes: str = ''
    ) -> Case:
        """
        Assign an L0 officer to a case. Overwrites existing assignment.
        
        Args:
            case: Case to assign (will be locked with select_for_update)
            officer: L0 officer to assign
            assigned_by: L1 user making the assignment
            notes: Optional assignment notes
            
        Returns:
            Updated Case object
            
        Raises:
            InvalidOfficerError: If officer is not L0 or not from same station
            InvalidAssignerError: If assigner is not L1 or not from same station
            CaseNotAssignableError: If case cannot be assigned
        """
        # Pre-validate inputs (before transaction)
        cls._validate_assigner(assigned_by, case)
        cls._validate_officer(officer, case)
        
        old_officer = None
        
        with transaction.atomic():
            # Lock case row for update to prevent race conditions
            locked_case = Case.objects.select_for_update().get(id=case.id)
            
            # Validate case state (inside transaction with lock)
            cls._validate_case_assignable(locked_case)
            
            now = timezone.now()
            old_status = locked_case.status
            old_level = locked_case.current_level
            old_officer = locked_case.assigned_officer
            
            # Update case (overwrites existing assignment)
            locked_case.assigned_officer = officer
            locked_case.assigned_by = assigned_by
            locked_case.assigned_at = now
            locked_case.status = CaseStatus.ASSIGNED
            locked_case.current_level = 'L0'
            locked_case.save(update_fields=[
                'assigned_officer',
                'assigned_by',
                'assigned_at',
                'status',
                'current_level',
                'updated_at'
            ])
            
            # Record status change
            if old_officer:
                reason = notes or f"Reassigned from {old_officer.identifier} to {officer.identifier}"
            else:
                reason = notes or f"Assigned to {officer.identifier}"
            
            CaseStatusHistory.objects.create(
                case=locked_case,
                from_status=old_status,
                to_status=CaseStatus.ASSIGNED,
                from_level=old_level,
                to_level='L0',
                changed_by=assigned_by,
                reason=reason,
                is_auto_escalation=False,
            )
            
            # Log assignment in escalation history
            EscalationHistory.objects.create(
                case=locked_case,
                event_type=EventType.ASSIGNMENT,
                from_level=old_level,
                to_level='L0',
                escalation_type=None,
                escalated_by=assigned_by,
                assigned_officer=officer,
                reason=reason
            )
            
            # Add system message for assignment
            from reports.services.investigation import InvestigationService
            if old_officer:
                msg = f"Case reassigned from {old_officer.identifier} to {officer.identifier} by {assigned_by.identifier}."
            else:
                msg = f"Case assigned to {officer.identifier} by {assigned_by.identifier}."
            InvestigationService.send_system_message(case=locked_case, text=msg)
        
        # Notify officers (outside transaction)
        try:
            from notifications.services import NotificationService
            if old_officer and old_officer != officer:
                NotificationService.notify_case_unassigned(locked_case, old_officer, assigned_by, "Reassigned to another officer")
            NotificationService.notify_case_assigned(locked_case, officer, assigned_by)
        except Exception:
            pass  # Don't fail assignment if notification fails
        
        return locked_case
    
    @classmethod
    def get_available_officers(cls, case: Case) -> List[User]:
        """
        Get list of L0 officers available for assignment.
        
        Officers must be:
        - Role L0
        - Same station as case
        - Active and not deleted
        """
        if not case.police_station:
            return []
        
        return list(
            User.objects.filter(
                role=UserRole.L0,
                police_station=case.police_station,
                is_active=True,
                is_deleted=False,
                status='active'
            ).order_by('identifier')
        )
    
    @classmethod
    def get_officer_workload(cls, officer: User) -> dict:
        """Get workload statistics for an officer."""
        from django.db.models import Count, Q
        
        assigned_cases = Case.objects.filter(
            assigned_officer=officer,
            is_deleted=False
        )
        
        stats = assigned_cases.aggregate(
            total=Count('id'),
            assigned=Count('id', filter=Q(status=CaseStatus.ASSIGNED)),
            in_progress=Count('id', filter=Q(status=CaseStatus.IN_PROGRESS)),
        )
        
        return stats
    
    @classmethod
    def _validate_assigner(cls, user: User, case: Case) -> None:
        """Validate user can assign officers to this case."""
        if user.role != UserRole.L1:
            raise InvalidAssignerError(
                f"Only L1 can assign officers. Got: {user.role}"
            )
        
        if case.police_station != user.police_station:
            raise InvalidAssignerError(
                "L1 can only assign officers to cases at their own station"
            )
    
    @classmethod
    def _validate_officer(cls, officer: User, case: Case) -> None:
        """Validate officer can be assigned to this case."""
        if officer.role != UserRole.L0:
            raise InvalidOfficerError(
                f"Only L0 officers can be assigned. Got: {officer.role}"
            )
        
        if not officer.is_active or officer.is_deleted:
            raise InvalidOfficerError("Officer account is not active")
        
        if getattr(officer, 'status', 'active') != 'active':
            raise InvalidOfficerError(f"Officer status must be active. Got: {officer.status}")
        
        if case.police_station and officer.police_station != case.police_station:
            raise InvalidOfficerError(
                "Officer must belong to the same police station as the case"
            )
    
    @classmethod
    def _validate_case_assignable(cls, case: Case) -> None:
        """Validate case can accept an assignment."""
        if case.status in CaseStatus.TERMINAL_STATES:
            raise CaseNotAssignableError(
                f"Cannot assign officers to {case.status} cases"
            )
        
        if case.current_level not in ['L0', 'L1', 'L2']:
            raise CaseNotAssignableError(
                f"Can only assign officers to station-level cases. Level: {case.current_level}"
            )
