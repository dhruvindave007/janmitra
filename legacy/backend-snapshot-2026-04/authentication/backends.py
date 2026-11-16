"""
Custom JWT authentication backend for JanMitra.

Implements device-bound JWT authentication:
- Tokens are bound to specific devices
- Validates device fingerprint on each request
- Checks user status (revoked, suspended)
- Enforces one-device-only rule for JanMitra members

Security features:
- Device fingerprint validation
- Token revocation checking
- User status verification
- Comprehensive audit logging
"""

import logging
from django.utils import timezone
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from audit.models import AuditLog, AuditEventType

security_logger = logging.getLogger('janmitra.security')


class DeviceBoundJWTAuthentication(JWTAuthentication):
    """
    Extended JWT authentication with device binding.
    
    Every request must include:
    - Authorization: Bearer <token>
    - X-Device-Fingerprint: <device_fingerprint>
    
    The device fingerprint is validated against the active session.
    """
    
    def authenticate(self, request):
        """
        Authenticate the request and validate device binding.
        
        Returns:
            tuple: (user, validated_token) if successful
        
        Raises:
            InvalidToken: If token or device validation fails
        """
        # First, perform standard JWT authentication
        result = super().authenticate(request)
        
        if result is None:
            return None
        
        user, validated_token = result
        
        # Check user status
        self._check_user_status(user, request)
        
        # For JanMitra members, validate device binding
        if user.is_janmitra:
            self._validate_device_binding(user, request, validated_token)
        
        # Update last activity
        self._update_activity(user, request)
        
        return (user, validated_token)
    
    def _check_user_status(self, user, request):
        """
        Check if user account is in valid status.
        
        Raises:
            InvalidToken: If user is revoked, suspended, or inactive
        """
        if user.is_revoked:
            security_logger.warning(
                f"Revoked user attempted access: {user.id} from {self._get_ip(request)}"
            )
            AuditLog.log(
                event_type=AuditEventType.AUTH_TOKEN_REVOKED,
                actor=user,
                request=request,
                success=False,
                description="Revoked user attempted API access"
            )
            raise InvalidToken({
                'detail': 'Your access has been revoked.',
                'code': 'access_revoked'
            })
        
        if user.status == 'suspended':
            raise InvalidToken({
                'detail': 'Your account is temporarily suspended.',
                'code': 'account_suspended'
            })
        
        if not user.is_active:
            raise InvalidToken({
                'detail': 'Your account is not active.',
                'code': 'account_inactive'
            })
    
    def _validate_device_binding(self, user, request, token):
        """
        Validate that the request comes from the registered device.
        
        For JanMitra members, each account is bound to exactly one device.
        The device fingerprint must match the active session.
        """
        from authentication.models import DeviceSession
        
        # Get device fingerprint from header
        device_fingerprint = request.META.get('HTTP_X_DEVICE_FINGERPRINT', '')
        
        if not device_fingerprint:
            security_logger.warning(
                f"Missing device fingerprint: user={user.id}, ip={self._get_ip(request)}"
            )
            raise InvalidToken({
                'detail': 'Device verification required.',
                'code': 'missing_device_fingerprint'
            })
        
        # Find active session for this user
        try:
            active_session = DeviceSession.objects.get(
                user=user,
                is_active=True
            )
        except DeviceSession.DoesNotExist:
            security_logger.warning(
                f"No active session for user: {user.id}"
            )
            raise InvalidToken({
                'detail': 'No active session found. Please log in again.',
                'code': 'no_active_session'
            })
        
        # Verify device fingerprint
        if not active_session.verify_fingerprint(device_fingerprint):
            security_logger.warning(
                f"Device fingerprint mismatch: user={user.id}, ip={self._get_ip(request)}"
            )
            AuditLog.log(
                event_type=AuditEventType.SYSTEM_SECURITY_ALERT,
                actor=user,
                request=request,
                success=False,
                description="Device fingerprint mismatch - possible token theft",
                metadata={
                    'expected_hash': active_session.device_fingerprint_hash[:16] + '...',
                    'received_hash': DeviceSession.hash_fingerprint(device_fingerprint)[:16] + '...',
                }
            )
            raise InvalidToken({
                'detail': 'Device verification failed.',
                'code': 'device_mismatch'
            })
    
    def _update_activity(self, user, request):
        """Update last activity timestamp for the active session."""
        from authentication.models import DeviceSession
        
        if user.is_janmitra:
            DeviceSession.objects.filter(
                user=user,
                is_active=True
            ).update(
                last_activity_at=timezone.now(),
                last_activity_ip=self._get_ip(request)
            )
    
    def _get_ip(self, request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class JanMitraTokenObtainMixin:
    """
    Mixin for token obtain serializers.
    
    Adds:
    - Device fingerprint to token claims
    - Session creation
    - Audit logging
    """
    
    @classmethod
    def get_token(cls, user, device_fingerprint=None, device_info=None):
        """
        Generate token with device binding claims.
        """
        from rest_framework_simplejwt.tokens import RefreshToken
        from authentication.models import DeviceSession
        
        token = RefreshToken.for_user(user)
        
        # Add custom claims
        token['role'] = user.role
        token['is_anonymous'] = user.is_anonymous
        
        # For JanMitra members, create device session
        if user.is_janmitra and device_fingerprint:
            session = DeviceSession.create_session(
                user=user,
                device_fingerprint=device_fingerprint,
                device_info=device_info or {}
            )
            token['session_id'] = str(session.id)
            
            # Store JTI in session for revocation
            session.refresh_token_jti = str(token['jti'])
            session.save(update_fields=['refresh_token_jti'])
        
        return token
