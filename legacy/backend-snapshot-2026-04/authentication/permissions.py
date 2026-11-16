"""
Custom permissions for JanMitra Backend.

Implements role-based access control:
- Level 1 (Highest Authority): Full access
- Level 2 (Field Authority): Report handling, escalation
- Level 3 (JanMitra): Report submission, status viewing

All permissions check user status and role.
"""

from rest_framework import permissions


class IsAuthenticated(permissions.IsAuthenticated):
    """
    Extended IsAuthenticated that also checks user status.
    """
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Check user status
        user = request.user
        if user.is_revoked or not user.is_active:
            return False
        
        return True


class IsLevel1(permissions.BasePermission):
    """
    Permission for Level 1 (Highest Authority) only.
    
    Level 1 has:
    - Final decision-making power
    - Escalation approval
    - Identity reveal approval
    - Decryption authorization
    - Full audit visibility
    - User revocation power
    """
    
    message = "This action requires Level 1 authority."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_revoked or not request.user.is_active:
            return False
        
        return request.user.is_level_1


class IsLevel2(permissions.BasePermission):
    """
    Permission for Level 2 (Field Authority) only.
    
    Level 2 has:
    - Report receiving and validation
    - Report rejection
    - Escalation to Level 1
    - Cannot see JanMitra identity (by default)
    """
    
    message = "This action requires Level 2 authority."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_revoked or not request.user.is_active:
            return False
        
        return request.user.is_level_2


class IsLevel1OrLevel2(permissions.BasePermission):
    """
    Permission for any authority (Level 1 or Level 2).
    """
    
    message = "This action requires authority access."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_revoked or not request.user.is_active:
            return False
        
        return request.user.is_authority


class IsJanMitra(permissions.BasePermission):
    """
    Permission for JanMitra members only.
    
    JanMitra members can:
    - Submit encrypted reports
    - Upload encrypted media
    - View their report status
    - Cannot see other members
    """
    
    message = "This action is for JanMitra members only."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_revoked or not request.user.is_active:
            return False
        
        return request.user.is_janmitra


class IsJanMitraOrAuthority(permissions.BasePermission):
    """
    Permission for any authenticated user (JanMitra or Authority).
    """
    
    message = "Authentication required."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_revoked or not request.user.is_active:
            return False
        
        return True


class CanViewReport(permissions.BasePermission):
    """
    Object-level permission for viewing a specific report.
    
    Rules:
    - JanMitra can view their own reports
    - Level 2 can view reports in their jurisdiction
    - Level 2 can view reports assigned to them
    - Level 1 can view all reports
    """
    
    message = "You do not have permission to view this report."
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Level 1 can view all reports
        if user.is_level_1:
            return True
        
        # Level 2 can view assigned reports or jurisdiction reports
        if user.is_level_2:
            if obj.assigned_to == user:
                return True
            # Check jurisdiction
            if hasattr(user, 'authority_profile'):
                if obj.jurisdiction_code == user.authority_profile.jurisdiction_code:
                    return True
            # Check if escalated to this user
            if obj.escalated_to == user:
                return True
            return False
        
        # JanMitra can view their own reports
        if user.is_janmitra:
            return obj.submitted_by == user
        
        return False


class CanModifyReport(permissions.BasePermission):
    """
    Object-level permission for modifying a specific report.
    
    Rules:
    - JanMitra can modify their draft reports
    - Level 2 can update status of assigned reports
    - Level 1 can modify any report
    """
    
    message = "You do not have permission to modify this report."
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Level 1 can modify all reports
        if user.is_level_1:
            return True
        
        # Level 2 can modify assigned reports
        if user.is_level_2:
            return obj.assigned_to == user or obj.escalated_to == user
        
        # JanMitra can only modify their draft reports
        if user.is_janmitra:
            return obj.submitted_by == user and obj.status == 'draft'
        
        return False


class CanEscalateReport(permissions.BasePermission):
    """
    Permission for escalating a report.
    
    Only Level 2 can escalate reports assigned to them.
    """
    
    message = "You do not have permission to escalate this report."
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_level_2:
            return False
        
        # Must be assigned to this user
        return obj.assigned_to == user


class CanApproveEscalation(permissions.BasePermission):
    """
    Permission for approving escalations.
    
    Only Level 1 can approve escalations.
    """
    
    message = "Only Level 1 authority can approve escalations."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_level_1
    
    def has_object_permission(self, request, view, obj):
        # Escalation must be directed to this user or any Level 1
        return request.user.is_level_1


class CanApproveIdentityReveal(permissions.BasePermission):
    """
    Permission for approving identity reveal requests.
    
    Only Level 1 can approve identity reveals.
    This is a critical security permission.
    """
    
    message = "Only Level 1 authority can approve identity reveals."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_level_1


class CanAuthorizeDecryption(permissions.BasePermission):
    """
    Permission for authorizing report decryption.
    
    Only Level 1 can authorize decryption for lawful access.
    """
    
    message = "Only Level 1 authority can authorize decryption."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_level_1


class CanRevokeUser(permissions.BasePermission):
    """
    Permission for revoking user access.
    
    Only Level 1 can revoke JanMitra members.
    Level 1 cannot revoke other Level 1 users.
    """
    
    message = "You do not have permission to revoke user access."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_level_1
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Cannot revoke self
        if obj == user:
            return False
        
        # Level 1 cannot revoke other Level 1 (would need higher authority)
        if obj.is_level_1:
            return False
        
        return user.is_level_1


class CanViewAuditLogs(permissions.BasePermission):
    """
    Permission for viewing audit logs.
    
    Only Level 1 can view audit logs.
    """
    
    message = "Only Level 1 authority can view audit logs."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_level_1


class CanIssueInviteCode(permissions.BasePermission):
    """
    Permission for issuing invite codes.
    
    Only authorities (Level 1 and Level 2) can issue invite codes.
    """
    
    message = "Only authorities can issue invite codes."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_authority


class CanDownloadMedia(permissions.BasePermission):
    """
    Permission for downloading incident media files.
    
    Rules:
    - Level-0 (Super Admin): CAN download
    - Level-1 (Senior Authority): CAN download
    - Level-2 Captain: CAN download
    - Level-2 (Field Authority): CANNOT download (preview only)
    - JanMitra: NO access at all
    
    This is for role-based media access control per PHASE 6.5 requirements.
    """
    
    message = "You do not have permission to download media files."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_revoked or not request.user.is_active:
            return False
        
        # JanMitra: NO access
        if request.user.is_janmitra:
            return False
        
        # Check user role for download permission
        from authentication.models import UserRole
        
        # Allowed roles for download
        allowed_roles = [
            UserRole.LEVEL_0,
            UserRole.LEVEL_1,
            UserRole.LEVEL_2_CAPTAIN,
        ]
        
        return request.user.role in allowed_roles


class CanPreviewMedia(permissions.BasePermission):
    """
    Permission for previewing incident media files (low-res/thumbnails).
    
    Rules:
    - All authority roles (Level-0, Level-1, Level-2 Captain, Level-2): CAN preview
    - JanMitra: NO access
    
    This allows Level-2 officers to see previews without download capability.
    """
    
    message = "You do not have permission to view media files."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_revoked or not request.user.is_active:
            return False
        
        # JanMitra: NO access
        if request.user.is_janmitra:
            return False
        
        # All authority roles can preview
        return request.user.is_authority
