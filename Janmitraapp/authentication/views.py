"""
Authentication views for JanMitra Backend.

Provides REST API endpoints for:
- Authority login (email/password)
- JanMitra registration (invite code + device)
- JanMitra login (device-based)
- Token refresh
- Logout
- Invite code management
- User revocation
"""

from django.utils import timezone
from rest_framework import status, generics, views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.throttling import ScopedRateThrottle

from .models import User, UserStatus, InviteCode, DeviceSession
from .serializers import (
    AuthorityLoginSerializer,
    JanMitraRegistrationSerializer,
    JanMitraLoginSerializer,
    DeviceBoundTokenRefreshSerializer,
    LogoutSerializer,
    UserSerializer,
    JanMitraUserSerializer,
    InviteCodeSerializer,
    CreateInviteCodeSerializer,
)
from .permissions import (
    IsAuthenticated,
    IsLevel1,
    IsLevel1OrLevel2,
    CanRevokeUser,
    CanIssueInviteCode,
)
from audit.models import AuditLog, AuditEventType


class LoginThrottle(ScopedRateThrottle):
    """Rate limiting for login endpoints."""
    scope = 'login'


class UnifiedLoginView(views.APIView):
    """
    Unified login endpoint that auto-detects user type.
    
    POST /api/v1/auth/login/
    
    For Authority (email + password):
    {
        "identifier": "user@example.com",  // or "email" or "username"
        "password": "secure_password",
        "device_id": "optional_device_id"
    }
    
    For JanMitra (device-only, no password):
    {
        "device_id": "unique_device_id"
    }
    
    Or with explicit user_type:
    {
        "user_type": "authority" | "janmitra",
        ...
    }
    
    Response:
    {
        "refresh": "jwt_refresh_token",
        "access": "jwt_access_token",
        "user": { ... }
    }
    """
    
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]
    
    def post(self, request):
        import logging
        logger = logging.getLogger('janmitra.auth')
        
        # Log incoming request for debugging
        logger.info(f"Login attempt - Raw data keys: {list(request.data.keys())}")
        
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        
        # Normalize field names - accept common aliases
        # identifier aliases: email, username, phone
        if 'identifier' not in data:
            data['identifier'] = data.get('email') or data.get('username') or data.get('phone') or ''
        
        # device_fingerprint aliases: device_id, deviceId
        if 'device_fingerprint' not in data:
            data['device_fingerprint'] = data.get('device_id') or data.get('deviceId') or ''
        
        logger.info(f"Login attempt - Normalized: identifier={bool(data.get('identifier'))}, password={bool(data.get('password'))}, device={bool(data.get('device_fingerprint'))}")
        
        # Explicit user_type takes priority
        user_type = data.get('user_type', '').lower()
        
        if user_type == 'janmitra':
            return self._janmitra_login(request, data)
        elif user_type == 'authority':
            return self._authority_login(request, data)
        
        # Auto-detect based on payload
        # If password is provided, it's authority login
        # If only device_id/device_fingerprint, it's JanMitra
        has_password = bool(data.get('password'))
        has_identifier = bool(data.get('identifier'))
        
        if has_password and has_identifier:
            return self._authority_login(request, data)
        elif not has_password and data.get('device_fingerprint'):
            return self._janmitra_login(request, data)
        elif has_password and not has_identifier:
            logger.warning(f"Login failed - has password but no identifier")
            return Response(
                {'detail': 'Missing identifier. Provide email, username, or identifier field.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        else:
            logger.warning(f"Login failed - invalid payload structure")
            return Response(
                {'detail': 'Invalid login payload. Provide identifier+password for authority or device_id for JanMitra.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _authority_login(self, request, data):
        """Handle authority login."""
        import logging
        logger = logging.getLogger('janmitra.auth')
        logger.info(f"[AUTHORITY LOGIN] Attempting with data keys: {list(data.keys())}")
        
        serializer = AuthorityLoginSerializer(
            data=data,
            context={'request': request}
        )
        if not serializer.is_valid():
            logger.error(f"[AUTHORITY LOGIN] Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        result = serializer.save()
        logger.info(f"[AUTHORITY LOGIN] Success for user")
        return Response(result, status=status.HTTP_200_OK)
    
    def _janmitra_login(self, request, data):
        """Handle JanMitra login."""
        import logging
        logger = logging.getLogger('janmitra.auth')
        logger.info(f"[JANMITRA LOGIN] Attempting with device_fingerprint: {bool(data.get('device_fingerprint'))}")
        
        serializer = JanMitraLoginSerializer(
            data=data,
            context={'request': request}
        )
        if not serializer.is_valid():
            logger.error(f"[JANMITRA LOGIN] Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        result = serializer.save()
        logger.info(f"[JANMITRA LOGIN] Success")
        return Response(result, status=status.HTTP_200_OK)


class AuthorityLoginView(views.APIView):
    """
    Login endpoint for Level 1 and Level 2 authorities.
    
    POST /api/v1/auth/authority/login/
    
    Request:
    {
        "identifier": "user@example.com",
        "password": "secure_password",
        "device_fingerprint": "optional_device_id",
        "device_info": {
            "device_name": "iPhone 15",
            "device_type": "phone",
            "os_name": "iOS",
            "os_version": "17.0",
            "app_version": "1.0.0"
        }
    }
    
    Response:
    {
        "refresh": "jwt_refresh_token",
        "access": "jwt_access_token",
        "user": { ... }
    }
    """
    
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]
    serializer_class = AuthorityLoginSerializer
    
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)


class JanMitraRegistrationView(views.APIView):
    """
    Registration endpoint for JanMitra members.
    
    POST /api/v1/auth/janmitra/register/
    
    Request:
    {
        "invite_code": "JM-XXXX-XXXX-XXXX",
        "device_fingerprint": "unique_device_id",
        "device_info": {
            "device_name": "Pixel 8",
            "device_type": "phone",
            "os_name": "Android",
            "os_version": "14",
            "app_version": "1.0.0"
        }
    }
    
    Response:
    {
        "refresh": "jwt_refresh_token",
        "access": "jwt_access_token",
        "user": { ... }
    }
    
    Notes:
    - Invite code is required and must be valid
    - Device fingerprint is mandatory for device binding
    - One device = one account
    """
    
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]
    serializer_class = JanMitraRegistrationSerializer
    
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)


class JanMitraLoginView(views.APIView):
    """
    Login endpoint for JanMitra members (device-based).
    
    POST /api/v1/auth/janmitra/login/
    
    Request:
    {
        "device_fingerprint": "unique_device_id",
        "device_info": { ... }
    }
    
    Response:
    {
        "refresh": "jwt_refresh_token",
        "access": "jwt_access_token",
        "user": { ... }
    }
    
    Notes:
    - JanMitra members authenticate via device fingerprint
    - No password required
    - Device must be previously registered
    """
    
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]
    serializer_class = JanMitraLoginSerializer
    
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)


class TokenRefreshView(views.APIView):
    """
    Token refresh endpoint with device validation.
    
    POST /api/v1/auth/token/refresh/
    
    Request:
    {
        "refresh": "jwt_refresh_token",
        "device_fingerprint": "optional_for_validation"
    }
    
    Response:
    {
        "access": "new_jwt_access_token",
        "refresh": "new_jwt_refresh_token"
    }
    """
    
    permission_classes = [AllowAny]
    serializer_class = DeviceBoundTokenRefreshSerializer
    
    def post(self, request):
        from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
        
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            return Response(
                {'detail': str(e), 'code': 'token_not_valid'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class LogoutView(views.APIView):
    """
    Logout endpoint.
    
    POST /api/v1/auth/logout/
    
    Request:
    {
        "refresh": "jwt_refresh_token"
    }
    
    This will:
    - Blacklist the refresh token
    - Invalidate the device session
    - Log the logout event
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer
    
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'detail': 'Successfully logged out.'},
            status=status.HTTP_200_OK
        )


class CurrentUserView(views.APIView):
    """
    Get current user information.
    
    GET /api/v1/auth/me/
    
    Returns the current authenticated user's information.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.is_janmitra:
            serializer = JanMitraUserSerializer(user)
        else:
            serializer = UserSerializer(user)
        
        return Response(serializer.data)


class InviteCodeListView(generics.ListAPIView):
    """
    List invite codes issued by the current user.
    
    GET /api/v1/auth/invites/
    
    Only authorities can view their issued invite codes.
    """
    
    permission_classes = [IsLevel1OrLevel2, CanIssueInviteCode]
    serializer_class = InviteCodeSerializer
    
    def get_queryset(self):
        return InviteCode.objects.filter(
            issued_by=self.request.user
        ).order_by('-created_at')


class InviteCodeCreateView(views.APIView):
    """
    Create a new invite code.
    
    POST /api/v1/auth/invites/
    
    Request:
    {
        "expires_in_days": 30,
        "max_uses": 1,
        "notes": "For trusted source"
    }
    
    Response:
    {
        "id": "uuid",
        "code": "JM-XXXX-XXXX-XXXX",
        ...
    }
    """
    
    permission_classes = [IsLevel1OrLevel2, CanIssueInviteCode]
    serializer_class = CreateInviteCodeSerializer
    
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        invite = serializer.save()
        return Response(
            InviteCodeSerializer(invite).data,
            status=status.HTTP_201_CREATED
        )


class RevokeUserView(views.APIView):
    """
    Revoke a user's access.
    
    POST /api/v1/auth/users/{user_id}/revoke/
    
    Request:
    {
        "reason": "Reason for revocation (required)"
    }
    
    This will:
    - Set user status to REVOKED
    - Invalidate all active sessions
    - Blacklist all active tokens
    - Log the revocation event
    
    Only Level 1 can revoke users.
    Level 1 cannot revoke other Level 1 users.
    """
    
    permission_classes = [IsLevel1, CanRevokeUser]
    
    def post(self, request, user_id):
        reason = request.data.get('reason', '').strip()
        
        if not reason:
            return Response(
                {'detail': 'Revocation reason is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        self.check_object_permissions(request, target_user)
        
        # Check if already revoked
        if target_user.is_revoked:
            return Response(
                {'detail': 'User access is already revoked.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Revoke access
        target_user.revoke_access(
            revoked_by=request.user,
            reason=reason
        )
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.USER_REVOKED,
            actor=request.user,
            target=target_user,
            request=request,
            success=True,
            description=f"User access revoked: {reason}",
            metadata={
                'target_user_id': str(target_user.id),
                'target_role': target_user.role,
                'reason': reason
            }
        )
        
        return Response(
            {'detail': 'User access has been revoked.'},
            status=status.HTTP_200_OK
        )


class DeviceSessionListView(generics.ListAPIView):
    """
    List device sessions for the current user.
    
    GET /api/v1/auth/sessions/
    
    Returns all sessions (active and inactive) for the current user.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        sessions = DeviceSession.objects.filter(
            user=request.user
        ).order_by('-last_activity_at')[:10]
        
        data = []
        for session in sessions:
            data.append({
                'id': str(session.id),
                'device_name': session.device_name,
                'device_type': session.device_type,
                'os_name': session.os_name,
                'os_version': session.os_version,
                'app_version': session.app_version,
                'is_active': session.is_active,
                'last_activity_at': session.last_activity_at.isoformat(),
                'created_at': session.created_at.isoformat(),
                'is_current': session.is_active,  # Simplified; could compare session IDs
            })
        
        return Response(data)


class InvalidateSessionView(views.APIView):
    """
    Invalidate a specific device session.
    
    POST /api/v1/auth/sessions/{session_id}/invalidate/
    
    Useful for logging out a specific device remotely.
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, session_id):
        try:
            session = DeviceSession.objects.get(
                id=session_id,
                user=request.user
            )
        except DeviceSession.DoesNotExist:
            return Response(
                {'detail': 'Session not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not session.is_active:
            return Response(
                {'detail': 'Session is already inactive.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session.invalidate(reason='SECURITY')
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.AUTH_DEVICE_INVALIDATED,
            actor=request.user,
            target=session,
            request=request,
            success=True,
            description="Device session invalidated by user",
            metadata={
                'session_id': str(session.id),
                'device_name': session.device_name
            }
        )
        
        return Response(
            {'detail': 'Session has been invalidated.'},
            status=status.HTTP_200_OK
        )
