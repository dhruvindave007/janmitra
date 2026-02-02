"""
Authentication models for JanMitra Backend.

Contains:
- Custom User model with role-based access control
- JanMitraProfile for anonymous citizen members
- AuthorityProfile for Level 1/Level 2 authorities
- DeviceSession for one-device enforcement
- InviteCode for invite-based registration

Security Features:
- UUID primary keys throughout
- Soft delete only
- Device binding
- Role-based permissions
"""

import uuid
import secrets
import hashlib
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.validators import RegexValidator

from core.models import BaseModel, SoftDeleteManager


class UserRole:
    """
    User role constants.
    
    LEVEL_0: Super admin - system administrator
    LEVEL_1: Senior authority - final decision maker
    LEVEL_2: Field authority - report handler  
    LEVEL_2_CAPTAIN: Level 2 captain - supervises Level 2 officers
    LEVEL_3 / JANMITRA: Anonymous citizen member
    """
    LEVEL_0 = 'level_0'
    LEVEL_1 = 'level_1'
    LEVEL_2 = 'level_2'
    LEVEL_2_CAPTAIN = 'level_2_captain'
    LEVEL_3 = 'level_3'  # JanMitra (alias below)
    JANMITRA = 'level_3'  # Alias for clarity
    
    CHOICES = [
        (LEVEL_0, 'Level 0 - Super Admin'),
        (LEVEL_1, 'Level 1 - Senior Authority'),
        (LEVEL_2, 'Level 2 - Field Authority'),
        (LEVEL_2_CAPTAIN, 'Level 2 Captain - Field Supervisor'),
        (LEVEL_3, 'Level 3 - JanMitra Member'),
    ]
    
    # Authority roles (non-anonymous)
    AUTHORITY_ROLES = [LEVEL_0, LEVEL_1, LEVEL_2, LEVEL_2_CAPTAIN]
    
    # All roles that can receive reports
    REPORT_RECEIVERS = [LEVEL_0, LEVEL_1, LEVEL_2, LEVEL_2_CAPTAIN]


class UserStatus:
    """User account status constants."""
    ACTIVE = 'active'
    SUSPENDED = 'suspended'
    REVOKED = 'revoked'
    PENDING = 'pending'
    
    CHOICES = [
        (ACTIVE, 'Active'),
        (SUSPENDED, 'Temporarily Suspended'),
        (REVOKED, 'Access Revoked'),
        (PENDING, 'Pending Activation'),
    ]


class UserManager(BaseUserManager):
    """
    Custom user manager for the JanMitra User model.
    Handles creation of regular users, authorities, and JanMitra members.
    """
    
    def get_queryset(self):
        """Return only non-deleted users by default."""
        return super().get_queryset().filter(is_deleted=False)
    
    def create_user(self, identifier, password=None, **extra_fields):
        """
        Create and return a regular user.
        
        Args:
            identifier: Unique identifier (phone/email for authority, anonymous ID for JanMitra)
            password: User password (required for authorities)
            **extra_fields: Additional fields
        """
        if not identifier:
            raise ValueError('User must have an identifier')
        
        user = self.model(identifier=identifier, **extra_fields)
        
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        
        user.save(using=self._db)
        return user
    
    def create_authority(self, identifier, password, role, **extra_fields):
        """
        Create an authority user (Level 1 or Level 2).
        
        Args:
            identifier: Email or phone number
            password: Strong password (required)
            role: UserRole.LEVEL_1 or UserRole.LEVEL_2
        """
        if role not in UserRole.AUTHORITY_ROLES:
            raise ValueError(f'Invalid authority role: {role}')
        
        if not password:
            raise ValueError('Authority users must have a password')
        
        extra_fields.setdefault('is_staff', role == UserRole.LEVEL_1)
        extra_fields['role'] = role
        extra_fields['status'] = UserStatus.ACTIVE
        
        return self.create_user(identifier, password, **extra_fields)
    
    def create_janmitra(self, device_fingerprint, invite_code_id, **extra_fields):
        """
        Create a JanMitra member (anonymous citizen).
        
        Args:
            device_fingerprint: Hashed device identifier
            invite_code_id: UUID of the used invite code
        """
        # Generate anonymous identifier
        anonymous_id = f"JM-{uuid.uuid4().hex[:12].upper()}"
        
        extra_fields['role'] = UserRole.LEVEL_3
        extra_fields['status'] = UserStatus.ACTIVE
        extra_fields['is_anonymous'] = True
        
        user = self.create_user(anonymous_id, password=None, **extra_fields)
        
        # Create associated JanMitra profile
        JanMitraProfile.objects.create(
            user=user,
            device_fingerprint_hash=device_fingerprint,
            invite_code_id=invite_code_id
        )
        
        return user
    
    def create_superuser(self, identifier, password, **extra_fields):
        """Create a superuser for admin access."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.LEVEL_1)
        extra_fields.setdefault('status', UserStatus.ACTIVE)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(identifier, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    Custom User model for JanMitra.
    
    Design decisions:
    - Uses UUID primary key (inherited from BaseModel)
    - identifier field instead of username (flexible for phone/email/anonymous)
    - Role-based access control
    - Soft delete only
    - Device binding for JanMitra users
    
    Security features:
    - Password hashing via Django's built-in mechanism
    - Account status tracking
    - Login attempt tracking
    - IP logging for security audits
    """
    
    identifier = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique identifier (email for authorities, anonymous ID for JanMitra)"
    )
    
    role = models.CharField(
        max_length=20,
        choices=UserRole.CHOICES,
        default=UserRole.LEVEL_3,
        db_index=True,
        help_text="User role determining access level"
    )
    
    status = models.CharField(
        max_length=20,
        choices=UserStatus.CHOICES,
        default=UserStatus.PENDING,
        db_index=True,
        help_text="Current account status"
    )
    
    is_anonymous = models.BooleanField(
        default=False,
        help_text="True for JanMitra members (identity protected)"
    )
    
    is_staff = models.BooleanField(
        default=False,
        help_text="Designates whether user can access admin site"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether user account is active"
    )
    
    # Security tracking
    last_login_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of last successful login"
    )
    
    failed_login_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Count of consecutive failed login attempts"
    )
    
    last_failed_login = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last failed login attempt"
    )
    
    password_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when password was last changed"
    )
    
    # Revocation tracking
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when access was revoked"
    )
    
    revoked_by = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='revocations_issued',
        help_text="Authority who revoked this user's access"
    )
    
    revocation_reason = models.TextField(
        blank=True,
        help_text="Reason for revocation (audit requirement)"
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'identifier'
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = 'janmitra_users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['role', 'status']),
            models.Index(fields=['identifier']),
        ]
    
    def __str__(self):
        if self.is_anonymous:
            return f"JanMitra-{str(self.id)[:8]}"
        return self.identifier
    
    @property
    def is_level_0(self):
        """Check if user is Level 0 (super admin)."""
        return self.role == UserRole.LEVEL_0
    
    @property
    def is_level_1(self):
        """Check if user is Level 1 (senior authority)."""
        return self.role == UserRole.LEVEL_1
    
    @property
    def is_level_2(self):
        """Check if user is Level 2 (field authority)."""
        return self.role == UserRole.LEVEL_2
    
    @property
    def is_level_2_captain(self):
        """Check if user is Level 2 Captain (field supervisor)."""
        return self.role == UserRole.LEVEL_2_CAPTAIN
    
    @property
    def is_janmitra(self):
        """Check if user is a JanMitra member."""
        return self.role == UserRole.LEVEL_3
    
    @property
    def is_authority(self):
        """Check if user is an authority (Level 0, 1, 2 or Captain)."""
        return self.role in UserRole.AUTHORITY_ROLES
    
    @property
    def is_revoked(self):
        """Check if user access has been revoked."""
        return self.status == UserStatus.REVOKED
    
    def can_view_identity(self, target_user):
        """
        Check if this user can view another user's identity.
        
        Rules:
        - Level 1 can view after approved identity reveal request
        - Level 2 cannot view JanMitra identity
        - JanMitra cannot view other identities
        """
        if not self.is_level_1:
            return False
        
        # Additional check for approved reveal request should be done at view level
        return True
    
    def revoke_access(self, revoked_by, reason):
        """
        Revoke user's access to the system.
        
        This will:
        - Set status to REVOKED
        - Record revocation details
        - Invalidate all active sessions
        
        Args:
            revoked_by: User performing the revocation
            reason: Reason for revocation (required for audit)
        """
        self.status = UserStatus.REVOKED
        self.revoked_at = timezone.now()
        self.revoked_by = revoked_by
        self.revocation_reason = reason
        self.is_active = False
        self.save()
        
        # Invalidate all device sessions
        DeviceSession.objects.filter(user=self, is_active=True).update(
            is_active=False,
            invalidated_at=timezone.now(),
            invalidation_reason='ACCESS_REVOKED'
        )
    
    def record_failed_login(self, ip_address=None):
        """Record a failed login attempt for security monitoring."""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        self.save(update_fields=['failed_login_attempts', 'last_failed_login'])
    
    def record_successful_login(self, ip_address=None):
        """Record a successful login and reset failed attempts."""
        self.failed_login_attempts = 0
        self.last_failed_login = None
        self.last_login_ip = ip_address
        self.last_login = timezone.now()
        self.save(update_fields=[
            'failed_login_attempts', 
            'last_failed_login', 
            'last_login_ip', 
            'last_login'
        ])


class JanMitraProfile(BaseModel):
    """
    Profile for JanMitra members (anonymous citizens).
    
    Contains:
    - Device binding information
    - Invite code tracking
    - Activity statistics
    
    Security features:
    - Device fingerprint stored as hash only
    - No personally identifiable information
    - Identity reveal requires Level 1 approval
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='janmitra_profile'
    )
    
    # Device binding (hashed for security)
    device_fingerprint_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 hash of device fingerprint"
    )
    
    # Invite tracking
    invite_code = models.ForeignKey(
        'InviteCode',
        on_delete=models.PROTECT,
        related_name='registered_members',
        help_text="Invite code used for registration"
    )
    
    # Activity statistics (for reputation/trust scoring)
    total_reports_submitted = models.PositiveIntegerField(
        default=0,
        help_text="Total number of reports submitted"
    )
    
    verified_reports_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of reports verified as credible"
    )
    
    rejected_reports_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of reports rejected"
    )
    
    # Trust score (computed, 0-100)
    trust_score = models.PositiveSmallIntegerField(
        default=50,
        help_text="Trust score based on report history (0-100)"
    )
    
    # Identity reveal tracking
    identity_revealed = models.BooleanField(
        default=False,
        help_text="True if identity has been revealed (lawful access)"
    )
    
    identity_revealed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when identity was revealed"
    )
    
    identity_revealed_to = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='identities_revealed_to',
        help_text="Authority who received identity reveal"
    )
    
    class Meta:
        db_table = 'janmitra_profiles'
        verbose_name = 'JanMitra Profile'
        verbose_name_plural = 'JanMitra Profiles'
    
    def __str__(self):
        return f"JanMitra-{str(self.user_id)[:8]}"
    
    def update_trust_score(self):
        """
        Recalculate trust score based on report history.
        
        Formula: 50 (base) + (verified * 5) - (rejected * 10)
        Clamped to 0-100 range.
        """
        score = 50 + (self.verified_reports_count * 5) - (self.rejected_reports_count * 10)
        self.trust_score = max(0, min(100, score))
        self.save(update_fields=['trust_score'])
    
    def increment_report_count(self, status='submitted'):
        """Update report counts based on report status."""
        if status == 'submitted':
            self.total_reports_submitted += 1
        elif status == 'verified':
            self.verified_reports_count += 1
        elif status == 'rejected':
            self.rejected_reports_count += 1
        
        self.save()
        self.update_trust_score()


class AuthorityProfile(BaseModel):
    """
    Profile for authority users (Level 1 and Level 2).
    
    Contains:
    - Professional details
    - Jurisdiction information
    - Performance metrics
    
    Note: Unlike JanMitra, authorities are not anonymous.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='authority_profile'
    )
    
    # Professional details (generic, not police-specific)
    designation = models.CharField(
        max_length=100,
        help_text="Official designation/title"
    )
    
    department = models.CharField(
        max_length=200,
        help_text="Department or unit"
    )
    
    jurisdiction_code = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Jurisdiction/area code"
    )
    
    jurisdiction_name = models.CharField(
        max_length=200,
        help_text="Human-readable jurisdiction name"
    )
    
    # Contact (encrypted at rest in production)
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?[1-9]\d{6,14}$',
                message='Enter a valid phone number'
            )
        ]
    )
    
    contact_email = models.EmailField(
        blank=True,
        help_text="Official email address"
    )
    
    # Supervision hierarchy
    supervisor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='subordinates',
        help_text="Supervising authority"
    )
    
    # Performance tracking
    reports_handled = models.PositiveIntegerField(
        default=0,
        help_text="Total reports handled"
    )
    
    reports_escalated = models.PositiveIntegerField(
        default=0,
        help_text="Reports escalated to higher authority"
    )
    
    avg_response_time_hours = models.FloatField(
        default=0.0,
        help_text="Average response time in hours"
    )
    
    class Meta:
        db_table = 'authority_profiles'
        verbose_name = 'Authority Profile'
        verbose_name_plural = 'Authority Profiles'
        indexes = [
            models.Index(fields=['jurisdiction_code']),
        ]
    
    def __str__(self):
        return f"{self.designation} - {self.jurisdiction_name}"


class DeviceSession(BaseModel):
    """
    Device session for one-device enforcement.
    
    Core security feature:
    - One JanMitra account = one device only
    - New login invalidates previous device
    - Tokens are device-bound
    
    Device fingerprint includes:
    - Device model
    - OS version
    - Unique device ID (hashed)
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='device_sessions'
    )
    
    # Device identification (hashed)
    device_fingerprint_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 hash of device fingerprint"
    )
    
    # Device metadata (for display/debugging, not security-critical)
    device_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Human-readable device name"
    )
    
    device_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Device type (phone/tablet)"
    )
    
    os_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Operating system name"
    )
    
    os_version = models.CharField(
        max_length=20,
        blank=True,
        help_text="Operating system version"
    )
    
    app_version = models.CharField(
        max_length=20,
        blank=True,
        help_text="JanMitra app version"
    )
    
    # Session status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this session is currently active"
    )
    
    # Token tracking
    refresh_token_jti = models.CharField(
        max_length=255,
        blank=True,
        help_text="JWT ID of current refresh token"
    )
    
    # Activity tracking
    last_activity_at = models.DateTimeField(
        auto_now=True,
        help_text="Last activity timestamp"
    )
    
    last_activity_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of last activity"
    )
    
    # Push notification token
    push_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="FCM/APNs token for push notifications"
    )
    
    # Invalidation tracking
    invalidated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When session was invalidated"
    )
    
    invalidation_reason = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('NEW_DEVICE', 'New device login'),
            ('LOGOUT', 'User logout'),
            ('ACCESS_REVOKED', 'Access revoked'),
            ('SECURITY', 'Security invalidation'),
            ('EXPIRED', 'Session expired'),
        ],
        help_text="Reason for invalidation"
    )
    
    class Meta:
        db_table = 'device_sessions'
        verbose_name = 'Device Session'
        verbose_name_plural = 'Device Sessions'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['device_fingerprint_hash']),
        ]
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.user} - {self.device_name or 'Unknown'} ({status})"
    
    def invalidate(self, reason='LOGOUT'):
        """Invalidate this device session."""
        self.is_active = False
        self.invalidated_at = timezone.now()
        self.invalidation_reason = reason
        self.save(update_fields=['is_active', 'invalidated_at', 'invalidation_reason'])
    
    @classmethod
    def create_session(cls, user, device_fingerprint, device_info=None):
        """
        Create a new device session, invalidating any existing active sessions.
        
        This enforces one-device-only rule for JanMitra users.
        """
        device_info = device_info or {}
        
        # Invalidate all existing active sessions for this user
        cls.objects.filter(user=user, is_active=True).update(
            is_active=False,
            invalidated_at=timezone.now(),
            invalidation_reason='NEW_DEVICE'
        )
        
        # Create new session
        return cls.objects.create(
            user=user,
            device_fingerprint_hash=cls.hash_fingerprint(device_fingerprint),
            device_name=device_info.get('device_name', ''),
            device_type=device_info.get('device_type', ''),
            os_name=device_info.get('os_name', ''),
            os_version=device_info.get('os_version', ''),
            app_version=device_info.get('app_version', ''),
            last_activity_ip=device_info.get('ip_address'),
        )
    
    @staticmethod
    def hash_fingerprint(fingerprint):
        """Hash device fingerprint using SHA-256."""
        return hashlib.sha256(fingerprint.encode()).hexdigest()
    
    def verify_fingerprint(self, fingerprint):
        """Verify if provided fingerprint matches stored hash."""
        return self.device_fingerprint_hash == self.hash_fingerprint(fingerprint)


class InviteCode(BaseModel):
    """
    Invite codes for JanMitra registration.
    
    JanMitra members can only register using valid invite codes
    issued by authorities. This ensures controlled onboarding.
    
    Features:
    - One-time use codes
    - Expiration support
    - Tracking of issuer and usage
    """
    
    code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="The invite code string"
    )
    
    issued_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='invite_codes_issued',
        help_text="Authority who issued this code"
    )
    
    # Usage tracking
    is_used = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether code has been used"
    )
    
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the code was used"
    )
    
    used_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invite_code_used',
        help_text="User who used this code"
    )
    
    # Validity
    expires_at = models.DateTimeField(
        help_text="Expiration timestamp"
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this invite"
    )
    
    max_uses = models.PositiveIntegerField(
        default=1,
        help_text="Maximum number of times code can be used"
    )
    
    use_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times code has been used"
    )
    
    class Meta:
        db_table = 'invite_codes'
        verbose_name = 'Invite Code'
        verbose_name_plural = 'Invite Codes'
        indexes = [
            models.Index(fields=['code', 'is_used']),
            models.Index(fields=['issued_by', 'is_used']),
        ]
    
    def __str__(self):
        return f"{self.code} (by {self.issued_by})"
    
    @classmethod
    def generate_code(cls, issued_by, expires_in_days=30, notes=''):
        """
        Generate a new invite code.
        
        Code format: JM-XXXX-XXXX-XXXX (uppercase alphanumeric)
        """
        # Generate secure random code
        code_chars = secrets.token_hex(6).upper()
        code = f"JM-{code_chars[:4]}-{code_chars[4:8]}-{code_chars[8:]}"
        
        return cls.objects.create(
            code=code,
            issued_by=issued_by,
            expires_at=timezone.now() + timezone.timedelta(days=expires_in_days),
            notes=notes
        )
    
    @property
    def is_valid(self):
        """Check if invite code is valid for use."""
        if self.is_deleted:
            return False
        if self.use_count >= self.max_uses:
            return False
        if timezone.now() > self.expires_at:
            return False
        return True
    
    def use(self, user):
        """Mark the code as used."""
        self.use_count += 1
        self.used_at = timezone.now()
        self.used_by = user
        
        if self.use_count >= self.max_uses:
            self.is_used = True
        
        self.save()
