"""
Object-level access checks for cases and their media.

Role checks on a view ("is this an officer?") are not enough on their own:
every endpoint that takes a case, incident or media id must also confirm
that *this* officer may see *that* record. The rules themselves live in
``reports.models.visible_cases_for_user``; the helpers below apply them to a
single object so list, detail and action endpoints cannot drift apart.
"""

from rest_framework.exceptions import NotFound, PermissionDenied

from authentication.models import UserRole
from reports.models import Case, visible_cases_for_user

# Roles allowed to download original incident media. Everyone else with
# access to the case gets the reduced-resolution preview only.
#
# Legacy policy: "Level 2" field officers preview only; captains, Level 1
# and Level 0 may download. Under the L0-L4 hierarchy the field officer is
# L0, so L1 and above download and L0 previews.
MEDIA_DOWNLOAD_ROLES = frozenset({
    UserRole.L1, UserRole.L2, UserRole.L3, UserRole.L4,
    UserRole.LEVEL_0, UserRole.LEVEL_1, UserRole.LEVEL_2_CAPTAIN,
})


def can_download_incident_media(user):
    """True if ``user``'s role may download original (full-size) media."""
    if not getattr(user, 'is_authenticated', False):
        return False
    return user.role in MEDIA_DOWNLOAD_ROLES


def user_can_access_case(user, case):
    """True if ``case`` falls inside ``user``'s visibility scope."""
    return visible_cases_for_user(user).filter(pk=case.pk).exists()


def get_case_for_user(user, case_id, queryset=None):
    """
    Return the case with ``case_id`` if ``user`` may act on it.

    Raises ``NotFound`` when the case does not exist and ``PermissionDenied``
    when it exists but is outside the user's scope (another station, not
    assigned to this L0, not escalated to this L3, ...).
    """
    queryset = queryset if queryset is not None else Case.objects.all()
    try:
        case = queryset.get(id=case_id, is_deleted=False)
    except Case.DoesNotExist:
        raise NotFound('Case not found.')

    if not user_can_access_case(user, case):
        raise PermissionDenied('You do not have access to this case.')
    return case


def check_incident_access(user, incident):
    """
    Raise ``PermissionDenied`` unless ``user`` may see ``incident``'s case.

    Media hangs off the incident, and the incident's case carries the
    station / assignment / escalation scope.
    """
    case = Case.objects.filter(incident=incident, is_deleted=False).first()
    if case is None or not user_can_access_case(user, case):
        raise PermissionDenied('You do not have access to this incident.')
