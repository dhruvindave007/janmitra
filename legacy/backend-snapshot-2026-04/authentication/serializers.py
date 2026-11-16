"""
Serializers for JanMitra Authentication.

Handles:
- Authority login (email/password + optional device info)
- JanMitra registration (invite code + device fingerprint)
- Token refresh with device validation
- User profile serialization

Security features:
- Device binding on token generation
- Invite code validation
- Password validation
- Audit logging
"""

import hashlib
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from .models import (
    User, UserRole, UserStatus,
    JanMitraProfile, AuthorityProfile,
    DeviceSession, InviteCode
)
from audit.models import AuditLog, AuditEventType


class DeviceInfoSerializer(serializers.Serializer):
    """Device information for session tracking."""
    device_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    device_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    os_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    os_version = serializers.CharField(max_length=20, required=False, allow_blank=True)
    app_version = serializers.CharField(max_length=20, required=False, allow_blank=True)


class AuthorityLoginSerializer(serializers.Serializer):
    """
    Serializer for authority (Level 1/2) login.
    
    Authorities use email/phone + password authentication.
    Device binding is optional for authorities but recommended.
    """
    
    identifier = serializers.CharField(
        max_length=255,
        help_text="Email or phone number"
    )
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    device_fingerprint = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Device fingerprint for session tracking"
    )
    device_info = DeviceInfoSerializer(required=False)
    
    def validate(self, attrs):
        identifier = attrs.get('identifier')
        password = attrs.get('password')
        
        # Authenticate user
        user = authenticate(
            username=identifier,
            password=password
        )
        
        if not user:
            # Check if user exists for better error handling
            try:
                existing_user = User.objects.get(identifier=identifier)
                existing_user.record_failed_login()
                
                # Log failed attempt
                AuditLog.log(
                    event_type=AuditEventType.AUTH_LOGIN_FAILED,
                    actor=existing_user,
                    request=self.context.get('request'),
                    success=False,
                    description="Invalid password",
                    metadata={'identifier': identifier}
                )
            except User.DoesNotExist:
                AuditLog.log(
                    event_type=AuditEventType.AUTH_LOGIN_FAILED,
                    request=self.context.get('request'),
                    success=False,
                    description="Invalid identifier",
                    metadata={'identifier': identifier}
                )
            
            raise serializers.ValidationError({
                'detail': 'Invalid credentials.'
            })
        
        # Check if authority or JanMitra with password (demo mode)
        # In production, JanMitra uses device-only login
        # For development/demo, allow password-based JanMitra login
        if not user.is_authority and not user.is_janmitra:
            raise serializers.ValidationError({
                'detail': 'Invalid user role for this login method.'
            })
        
        # Check status
        if user.is_revoked:
            raise serializers.ValidationError({
                'detail': 'Your access has been revoked.'
            })
        
        if user.status == UserStatus.SUSPENDED:
            raise serializers.ValidationError({
                'detail': 'Your account is temporarily suspended.'
            })
        
        if not user.is_active:
            raise serializers.ValidationError({
                'detail': 'Your account is not active.'
            })
        
        attrs['user'] = user
        return attrs
    
    def create(self, validated_data):
        user = validated_data['user']
        request = self.context.get('request')
        device_fingerprint = validated_data.get('device_fingerprint', '')
        device_info = validated_data.get('device_info', {})
        
        # Record successful login
        ip_address = self._get_ip(request) if request else None
        user.record_successful_login(ip_address)
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        refresh['is_anonymous'] = False
        
        # Create device session if fingerprint provided
        if device_fingerprint:
            device_info['ip_address'] = ip_address
            session = DeviceSession.create_session(
                user=user,
                device_fingerprint=device_fingerprint,
                device_info=device_info
            )
            refresh['session_id'] = str(session.id)
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            actor=user,
            request=request,
            success=True,
            description="Authority login successful",
            metadata={
                'role': user.role,
                'device_bound': bool(device_fingerprint)
            }
        )
        
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'role': user.role,
            'user': UserSerializer(user).data
        }
    
    def _get_ip(self, request):
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class JanMitraRegistrationSerializer(serializers.Serializer):
    """
    Serializer for JanMitra member registration.
    
    JanMitra registration requires:
    - Valid invite code
    - Device fingerprint (mandatory for device binding)
    - Device info
    
    The registration creates an anonymous account with no personal info.
    """
    
    invite_code = serializers.CharField(
        max_length=20,
        help_text="Invite code provided by authority"
    )
    device_fingerprint = serializers.CharField(
        max_length=255,
        help_text="Unique device fingerprint"
    )
    device_info = DeviceInfoSerializer(required=False)
    
    def validate_invite_code(self, value):
        """Validate the invite code."""
        try:
            invite = InviteCode.objects.get(code=value.upper())
        except InviteCode.DoesNotExist:
            raise serializers.ValidationError("Invalid invite code.")
        
        if not invite.is_valid:
            if invite.is_deleted:
                raise serializers.ValidationError("This invite code has been revoked.")
            if invite.use_count >= invite.max_uses:
                raise serializers.ValidationError("This invite code has already been used.")
            if timezone.now() > invite.expires_at:
                raise serializers.ValidationError("This invite code has expired.")
            raise serializers.ValidationError("This invite code is no longer valid.")
        
        return invite
    
    def validate_device_fingerprint(self, value):
        """Check if device is already registered."""
        fingerprint_hash = hashlib.sha256(value.encode()).hexdigest()
        
        # Check if this device already has an active JanMitra account
        existing = JanMitraProfile.objects.filter(
            device_fingerprint_hash=fingerprint_hash,
            user__is_active=True,
            user__status=UserStatus.ACTIVE
        ).exists()
        
        if existing:
            raise serializers.ValidationError(
                "This device is already registered with a JanMitra account."
            )
        
        return value
    
    def create(self, validated_data):
        invite = validated_data['invite_code']
        device_fingerprint = validated_data['device_fingerprint']
        device_info = validated_data.get('device_info', {})
        request = self.context.get('request')
        
        # Hash the device fingerprint
        fingerprint_hash = hashlib.sha256(device_fingerprint.encode()).hexdigest()
        
        # Create user
        user = User.objects.create_janmitra(
            device_fingerprint=device_fingerprint,
            invite_code_id=invite.id
        )
        
        # Mark invite as used
        invite.use(user)
        
        # Create device session
        ip_address = self._get_ip(request) if request else None
        device_info['ip_address'] = ip_address
        session = DeviceSession.create_session(
            user=user,
            device_fingerprint=device_fingerprint,
            device_info=device_info
        )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        refresh['is_anonymous'] = True
        refresh['session_id'] = str(session.id)
        
        # Store JTI in session
        session.refresh_token_jti = str(refresh['jti'])
        session.save(update_fields=['refresh_token_jti'])
        
        # Audit logs
        AuditLog.log(
            event_type=AuditEventType.INVITE_USED,
            actor=user,
            target=invite,
            request=request,
            success=True,
            description="Invite code used for JanMitra registration",
            metadata={
                'invite_code': invite.code,
                'issued_by': str(invite.issued_by.id)
            }
        )
        
        AuditLog.log(
            event_type=AuditEventType.USER_CREATED,
            actor=user,
            request=request,
            success=True,
            description="JanMitra member registered",
            metadata={
                'role': UserRole.LEVEL_3,
                'device_registered': True
            }
        )
        
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'role': user.role,
            'user': JanMitraUserSerializer(user).data
        }
    
    def _get_ip(self, request):
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class JanMitraLoginSerializer(serializers.Serializer):
    """
    Serializer for JanMitra member login (device-based).
    
    JanMitra members authenticate using their device fingerprint.
    No password required - device binding is the authentication factor.
    """
    
    device_fingerprint = serializers.CharField(
        max_length=255,
        help_text="Unique device fingerprint"
    )
    device_info = DeviceInfoSerializer(required=False)
    
    def validate_device_fingerprint(self, value):
        """Find the JanMitra account for this device."""
        fingerprint_hash = hashlib.sha256(value.encode()).hexdigest()
        
        try:
            profile = JanMitraProfile.objects.select_related('user').get(
                device_fingerprint_hash=fingerprint_hash
            )
        except JanMitraProfile.DoesNotExist:
            raise serializers.ValidationError(
                "No JanMitra account found for this device."
            )
        
        user = profile.user
        
        # Check user status
        if user.is_revoked:
            raise serializers.ValidationError(
                "Your access has been revoked."
            )
        
        if user.status == UserStatus.SUSPENDED:
            raise serializers.ValidationError(
                "Your account is temporarily suspended."
            )
        
        if not user.is_active:
            raise serializers.ValidationError(
                "Your account is not active."
            )
        
        return {'fingerprint': value, 'user': user}
    
    def create(self, validated_data):
        fingerprint_data = validated_data['device_fingerprint']
        user = fingerprint_data['user']
        device_fingerprint = fingerprint_data['fingerprint']
        device_info = validated_data.get('device_info', {})
        request = self.context.get('request')
        
        # Record login
        ip_address = self._get_ip(request) if request else None
        user.record_successful_login(ip_address)
        
        # Create new device session (invalidates old ones)
        device_info['ip_address'] = ip_address
        session = DeviceSession.create_session(
            user=user,
            device_fingerprint=device_fingerprint,
            device_info=device_info
        )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        refresh['is_anonymous'] = True
        refresh['session_id'] = str(session.id)
        
        # Store JTI in session
        session.refresh_token_jti = str(refresh['jti'])
        session.save(update_fields=['refresh_token_jti'])
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            actor=user,
            request=request,
            success=True,
            description="JanMitra login via device fingerprint",
            metadata={
                'session_id': str(session.id)
            }
        )
        
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'role': user.role,
            'user': JanMitraUserSerializer(user).data
        }
    
    def _get_ip(self, request):
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class DeviceBoundTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Extended token refresh that validates device binding.
    """
    
    device_fingerprint = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True
    )
    
    def validate(self, attrs):
        # Get user/session info from the token BEFORE rotation blacklists it
        try:
            refresh = self.token_class(attrs['refresh'])
            user_id = refresh.payload.get('user_id')
            session_id = refresh.payload.get('session_id')
        except Exception:
            # Let parent handle invalid token
            user_id = None
            session_id = None
        
        # Standard token validation (this rotates/blacklists the old token)
        data = super().validate(attrs)
        
        if session_id:
            # Validate session is still active
            from .models import DeviceSession
            try:
                session = DeviceSession.objects.get(
                    id=session_id,
                    is_active=True
                )
            except DeviceSession.DoesNotExist:
                raise serializers.ValidationError({
                    'detail': 'Session has been invalidated. Please log in again.'
                })
            
            # Validate device fingerprint if provided
            device_fingerprint = attrs.get('device_fingerprint')
            if device_fingerprint and not session.verify_fingerprint(device_fingerprint):
                raise serializers.ValidationError({
                    'detail': 'Device verification failed.'
                })
        
        return data


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for authority users.
    Includes profile information.
    """
    
    profile = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'identifier', 'role', 'status',
            'is_active', 'last_login', 'created_at',
            'profile'
        ]
        read_only_fields = fields
    
    def get_profile(self, obj):
        if hasattr(obj, 'authority_profile'):
            return AuthorityProfileSerializer(obj.authority_profile).data
        return None


class JanMitraUserSerializer(serializers.ModelSerializer):
    """
    Serializer for JanMitra users.
    Limited information for privacy.
    """
    
    profile = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'identifier', 'role', 'status',
            'is_active', 'last_login', 'created_at',
            'profile'
        ]
        read_only_fields = fields
    
    def get_profile(self, obj):
        if hasattr(obj, 'janmitra_profile'):
            return JanMitraProfileSerializer(obj.janmitra_profile).data
        return None


class JanMitraProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for JanMitra profile.
    Shows limited information for privacy.
    """
    
    class Meta:
        model = JanMitraProfile
        fields = [
            'total_reports_submitted',
            'verified_reports_count',
            'rejected_reports_count',
            'trust_score',
            'created_at'
        ]
        read_only_fields = fields


class AuthorityProfileSerializer(serializers.ModelSerializer):
    """Serializer for authority profile."""
    
    class Meta:
        model = AuthorityProfile
        fields = [
            'designation', 'department',
            'jurisdiction_code', 'jurisdiction_name',
            'reports_handled', 'reports_escalated',
            'avg_response_time_hours'
        ]
        read_only_fields = fields


class LogoutSerializer(serializers.Serializer):
    """Serializer for logout."""
    
    refresh = serializers.CharField(
        help_text="Refresh token to blacklist"
    )
    
    def validate_refresh(self, value):
        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            RefreshToken(value)
        except Exception:
            raise serializers.ValidationError("Invalid refresh token.")
        return value
    
    def save(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
        
        refresh = self.validated_data['refresh']
        token = RefreshToken(refresh)
        
        # Blacklist the token
        token.blacklist()
        
        # Invalidate device session if exists
        session_id = token.payload.get('session_id')
        if session_id:
            DeviceSession.objects.filter(id=session_id).update(
                is_active=False,
                invalidated_at=timezone.now(),
                invalidation_reason='LOGOUT'
            )
        
        # Audit log
        user_id = token.payload.get('user_id')
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                AuditLog.log(
                    event_type=AuditEventType.AUTH_LOGOUT,
                    actor=user,
                    request=self.context.get('request'),
                    success=True,
                    description="User logged out"
                )
            except User.DoesNotExist:
                pass


class InviteCodeSerializer(serializers.ModelSerializer):
    """Serializer for invite codes."""
    
    issued_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = InviteCode
        fields = [
            'id', 'code', 'issued_by', 'issued_by_name',
            'is_used', 'used_at', 'expires_at',
            'max_uses', 'use_count', 'notes',
            'created_at'
        ]
        read_only_fields = [
            'id', 'code', 'issued_by', 'is_used',
            'used_at', 'use_count', 'created_at'
        ]
    
    def get_issued_by_name(self, obj):
        return obj.issued_by.identifier


class CreateInviteCodeSerializer(serializers.Serializer):
    """Serializer for creating invite codes."""
    
    expires_in_days = serializers.IntegerField(
        min_value=1,
        max_value=365,
        default=30,
        help_text="Number of days until code expires"
    )
    max_uses = serializers.IntegerField(
        min_value=1,
        max_value=10,
        default=1,
        help_text="Maximum number of times code can be used"
    )
    notes = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Internal notes about this invite"
    )
    
    def create(self, validated_data):
        user = self.context['request'].user
        
        invite = InviteCode.generate_code(
            issued_by=user,
            expires_in_days=validated_data.get('expires_in_days', 30),
            notes=validated_data.get('notes', '')
        )
        
        if validated_data.get('max_uses'):
            invite.max_uses = validated_data['max_uses']
            invite.save(update_fields=['max_uses'])
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.INVITE_CREATED,
            actor=user,
            target=invite,
            request=self.context.get('request'),
            success=True,
            description="Invite code created",
            metadata={
                'code': invite.code,
                'expires_at': invite.expires_at.isoformat(),
                'max_uses': invite.max_uses
            }
        )
        
        return invite
