"""
Services layer for reports module.

All business logic is centralized here:
- JurisdictionService: GPS-based police station routing
- AssignmentService: Officer assignment to cases
- EscalationService: SLA breach detection and auto-escalation
- InvestigationService: Chat message handling with access control
- BroadcastIncidentService: Incident creation workflow

Usage:
    from reports.services import (
        JurisdictionService,
        AssignmentService,
        EscalationService,
        InvestigationService,
        BroadcastIncidentService,
    )
"""

from .jurisdiction import JurisdictionService
from .assignment import (
    AssignmentService,
    AssignmentError,
    InvalidOfficerError,
    InvalidAssignerError,
    CaseNotAssignableError,
)
from .escalation import (
    EscalationService,
    EscalationError,
    CannotEscalateError,
)
from .investigation import (
    InvestigationService,
    InvestigationError,
    AccessDeniedError,
    ChatLockedError,
    InvalidMessageError,
)
from .broadcast import BroadcastIncidentService, IncidentCreationError

__all__ = [
    'JurisdictionService',
    'AssignmentService',
    'AssignmentError',
    'InvalidOfficerError',
    'InvalidAssignerError',
    'CaseNotAssignableError',
    'EscalationService',
    'EscalationError',
    'CannotEscalateError',
    'InvestigationService',
    'InvestigationError',
    'AccessDeniedError',
    'ChatLockedError',
    'InvalidMessageError',
    'BroadcastIncidentService',
    'IncidentCreationError',
]
