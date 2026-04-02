"""
InvestigationService: Chat message handling with access control.

Handles:
- Creating investigation messages
- Media attachment
- Access control (only authorized users can access case chat)
- System messages for automated events

Usage:
    from reports.services import InvestigationService
    
    # Send text message
    msg = InvestigationService.send_message(
        case=case,
        sender=user,
        text="Investigation update..."
    )
    
    # Send media message
    msg = InvestigationService.send_media_message(
        case=case,
        sender=user,
        file=uploaded_file,
        caption="Evidence photo"
    )
"""

from typing import Optional, List, BinaryIO
import mimetypes
import os

from django.db import transaction
from django.db.models import Q
from django.core.files.base import ContentFile
from django.utils import timezone

from authentication.models import User, UserRole
from reports.models import Case, CaseStatus, InvestigationMessage, MessageType


class InvestigationError(Exception):
    """Base exception for investigation errors."""
    pass


class AccessDeniedError(InvestigationError):
    """Raised when user doesn't have access to the case."""
    pass


class ChatLockedError(InvestigationError):
    """Raised when chat is locked (case closed)."""
    pass


class InvalidMessageError(InvestigationError):
    """Raised when message content is invalid."""
    pass


class InvestigationService:
    """
    Service for managing investigation chat messages.
    
    Access Control Rules:
    - L0: Only if assigned to the case
    - L1/L2: If case is at their police station
    - L3: If case is escalated to L3
    - L4: If case is escalated to L4
    - JANMITRA: No access (anonymous reporters cannot chat)
    
    Chat Rules:
    - Messages are immutable (no edits after creation)
    - Chat is locked when case is closed/rejected
    - System messages for automated events (escalation, assignment, etc.)
    """
    
    # Maximum text content length
    MAX_TEXT_LENGTH = 10000
    
    # Maximum file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    # Allowed MIME types
    ALLOWED_MIME_TYPES = [
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'video/mp4', 'video/quicktime', 'video/webm',
        'audio/mpeg', 'audio/wav', 'audio/ogg',
        'application/pdf',
        'text/plain',
    ]
    
    @classmethod
    def send_message(
        cls,
        case: Case,
        sender: User,
        text: str
    ) -> InvestigationMessage:
        """
        Send a text message to the case investigation chat.
        
        Args:
            case: Case to send message to
            sender: User sending the message
            text: Message text content
            
        Returns:
            Created InvestigationMessage
            
        Raises:
            AccessDeniedError: If user doesn't have access
            ChatLockedError: If chat is locked
            InvalidMessageError: If message is invalid
        """
        # Validate access and state
        cls._validate_access(case, sender)
        cls._validate_chat_open(case)
        cls._validate_text(text)
        
        with transaction.atomic():
            message = InvestigationMessage.objects.create(
                case=case,
                sender=sender,
                sender_role=sender.role,
                message_type=MessageType.TEXT,
                text_content=text.strip()
            )
        
        return message
    
    @classmethod
    def send_media_message(
        cls,
        case: Case,
        sender: User,
        file: BinaryIO,
        file_name: str,
        caption: str = ''
    ) -> InvestigationMessage:
        """
        Send a media message to the case investigation chat.
        
        Args:
            case: Case to send message to
            sender: User sending the message
            file: File object or file-like object
            file_name: Original filename
            caption: Optional text caption
            
        Returns:
            Created InvestigationMessage
            
        Raises:
            AccessDeniedError: If user doesn't have access
            ChatLockedError: If chat is locked
            InvalidMessageError: If file is invalid
        """
        # Validate access and state
        cls._validate_access(case, sender)
        cls._validate_chat_open(case)
        
        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        # Read file to get size
        if hasattr(file, 'seek'):
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
        elif hasattr(file, 'size'):
            file_size = file.size
        else:
            # Read all content to get size
            content = file.read()
            file_size = len(content)
            file = ContentFile(content, name=file_name)
        
        # Validate file
        cls._validate_file(file_name, mime_type, file_size)
        
        with transaction.atomic():
            message = InvestigationMessage.objects.create(
                case=case,
                sender=sender,
                sender_role=sender.role,
                message_type=MessageType.MEDIA,
                text_content=caption.strip() if caption else None,
                file_name=file_name,
                file_size=file_size,
                file_type=mime_type
            )
            
            # Save file without triggering full model save (message is immutable)
            message.file.save(file_name, file, save=False)
            # Update only the file field in database
            InvestigationMessage.objects.filter(id=message.id).update(file=message.file.name)
        
        return message
    
    @classmethod
    def send_system_message(
        cls,
        case: Case,
        text: str
    ) -> InvestigationMessage:
        """
        Send a system message (no sender, automated events).
        
        Used for:
        - Case assigned to officer
        - Case escalated
        - SLA breached
        - Case status changes
        
        Args:
            case: Case to send message to
            text: System message text
            
        Returns:
            Created InvestigationMessage
        """
        with transaction.atomic():
            message = InvestigationMessage.objects.create(
                case=case,
                sender=None,
                sender_role='SYSTEM',
                message_type=MessageType.SYSTEM,
                text_content=text.strip()
            )
        
        return message
    
    @classmethod
    def get_messages(
        cls,
        case: Case,
        user: User,
        limit: int = 50,
        before_id: Optional[str] = None,
        after_id: Optional[str] = None
    ) -> List[InvestigationMessage]:
        """
        Get investigation messages for a case.
        
        Args:
            case: Case to get messages for
            user: User requesting messages (for access check)
            limit: Maximum number of messages to return
            before_id: Get messages before this message ID (pagination)
            after_id: Get messages after this message ID (new messages)
            
        Returns:
            List of InvestigationMessage objects
            
        Raises:
            AccessDeniedError: If user doesn't have access
        """
        cls._validate_access(case, user)
        
        qs = InvestigationMessage.objects.filter(
            case=case,
            is_deleted=False
        ).select_related('sender')
        
        if before_id:
            # Get the timestamp of the reference message
            try:
                ref_msg = InvestigationMessage.objects.get(id=before_id)
                qs = qs.filter(created_at__lt=ref_msg.created_at)
            except InvestigationMessage.DoesNotExist:
                pass
        
        if after_id:
            try:
                ref_msg = InvestigationMessage.objects.get(id=after_id)
                qs = qs.filter(created_at__gt=ref_msg.created_at)
            except InvestigationMessage.DoesNotExist:
                pass
        
        # Order by created_at ascending (oldest first)
        qs = qs.order_by('created_at')
        
        if limit:
            if before_id:
                # For "load more" (older messages), get last N and reverse
                messages = list(qs.order_by('-created_at')[:limit])
                messages.reverse()
            else:
                messages = list(qs[:limit])
        else:
            messages = list(qs)
        
        return messages
    
    @classmethod
    def get_message_count(cls, case: Case, user: User) -> int:
        """
        Get total message count for a case.
        
        Args:
            case: Case to count messages for
            user: User requesting count (for access check)
            
        Returns:
            Total number of messages
        """
        cls._validate_access(case, user)
        
        return InvestigationMessage.objects.filter(
            case=case,
            is_deleted=False
        ).count()
    
    @classmethod
    def get_new_messages_count(
        cls,
        case: Case,
        user: User,
        since_id: str
    ) -> int:
        """
        Get count of new messages since a given message.
        
        Useful for showing "X new messages" badge.
        
        Args:
            case: Case to check
            user: User requesting count
            since_id: Message ID to count from
            
        Returns:
            Number of new messages
        """
        cls._validate_access(case, user)
        
        try:
            ref_msg = InvestigationMessage.objects.get(id=since_id)
        except InvestigationMessage.DoesNotExist:
            return 0
        
        return InvestigationMessage.objects.filter(
            case=case,
            created_at__gt=ref_msg.created_at,
            is_deleted=False
        ).count()
    
    @classmethod
    def can_user_access_case(cls, case: Case, user: User) -> bool:
        """
        Check if user has access to case investigation.
        
        Args:
            case: Case to check access for
            user: User to check
            
        Returns:
            True if user has access, False otherwise
        """
        try:
            cls._validate_access(case, user)
            return True
        except AccessDeniedError:
            return False
    
    @classmethod
    def lock_chat(cls, case: Case) -> None:
        """
        Lock the investigation chat (called when case is closed).
        
        Args:
            case: Case to lock chat for
        """
        case.is_chat_locked = True
        case.save(update_fields=['is_chat_locked', 'updated_at'])
        
        # Send system message
        cls.send_system_message(
            case,
            "Investigation chat has been locked. The case has been closed."
        )
    
    @classmethod
    def delete_message(
        cls,
        message: InvestigationMessage,
        deleted_by: User
    ) -> None:
        """
        Soft delete a message. Only the author can delete their own message.
        
        Args:
            message: Message to delete
            deleted_by: User attempting to delete
            
        Raises:
            AccessDeniedError: If user doesn't have access to the case
            PermissionError: If user is not the author or message is a system message
        """
        # First validate user has access to the case
        cls._validate_access(message.case, deleted_by)
        
        # Delegate to model's soft_delete method (handles author check)
        message.soft_delete(deleted_by)
    
    @classmethod
    def unlock_chat(cls, case: Case) -> None:
        """
        Unlock the investigation chat (e.g., case reopened).
        
        Args:
            case: Case to unlock chat for
        """
        case.is_chat_locked = False
        case.save(update_fields=['is_chat_locked', 'updated_at'])
        
        cls.send_system_message(
            case,
            "Investigation chat has been unlocked. The case has been reopened."
        )
    
    @classmethod
    def _validate_access(cls, case: Case, user: User) -> None:
        """
        Validate user has access to case investigation.
        
        Access rules:
        - L0: Only if assigned to the case
        - L1/L2: If case is at their police station
        - L3: If case is escalated AND from their assigned stations
        - L4: Always (full access)
        - JANMITRA/others: No access
        
        Raises:
            AccessDeniedError: If user doesn't have access
        """
        role = user.role
        
        # L4 has full access to all cases
        if role == UserRole.L4:
            return
        
        # L3 has access to escalated cases from their assigned stations
        if role == UserRole.L3:
            if case.current_level not in ['L3', 'L4']:
                raise AccessDeniedError(
                    "L3 can only access cases escalated to L3 or L4 level"
                )
            if not user.assigned_stations.filter(id=case.police_station_id).exists():
                raise AccessDeniedError(
                    "L3 can only access cases from their assigned stations"
                )
            return
        
        # L0 must be assigned to the case
        if role == UserRole.L0:
            if case.assigned_officer == user:
                return
            raise AccessDeniedError(
                "L0 officers can only access cases assigned to them"
            )
        
        # L1/L2 must be at the same station
        if role in [UserRole.L1, UserRole.L2]:
            if case.police_station == user.police_station:
                return
            raise AccessDeniedError(
                "L1/L2 officers can only access cases at their police station"
            )
        
        # All other roles (JANMITRA, legacy) have no access
        raise AccessDeniedError(
            f"Role {role} does not have access to investigation chat"
        )
    
    @classmethod
    def _validate_chat_open(cls, case: Case) -> None:
        """
        Validate chat is open for new messages.
        
        Args:
            case: Case to validate
            
        Raises:
            ChatLockedError: If chat is locked
        """
        if case.is_chat_locked:
            raise ChatLockedError("Investigation chat is locked")
        
        if case.status in [CaseStatus.CLOSED, CaseStatus.REJECTED]:
            raise ChatLockedError(
                f"Cannot send messages to {case.status} cases"
            )
    
    @classmethod
    def _validate_text(cls, text: str) -> None:
        """
        Validate message text content.
        
        Args:
            text: Text to validate
            
        Raises:
            InvalidMessageError: If text is invalid
        """
        if not text or not text.strip():
            raise InvalidMessageError("Message text cannot be empty")
        
        if len(text) > cls.MAX_TEXT_LENGTH:
            raise InvalidMessageError(
                f"Message text exceeds maximum length of {cls.MAX_TEXT_LENGTH} characters"
            )
    
    @classmethod
    def _validate_file(
        cls,
        file_name: str,
        mime_type: str,
        file_size: int
    ) -> None:
        """
        Validate file for media message.
        
        Args:
            file_name: Original filename
            mime_type: MIME type of file
            file_size: Size in bytes
            
        Raises:
            InvalidMessageError: If file is invalid
        """
        if not file_name:
            raise InvalidMessageError("File name is required")
        
        if file_size <= 0:
            raise InvalidMessageError("File cannot be empty")
        
        if file_size > cls.MAX_FILE_SIZE:
            max_mb = cls.MAX_FILE_SIZE / (1024 * 1024)
            raise InvalidMessageError(
                f"File size exceeds maximum of {max_mb}MB"
            )
        
        # Check MIME type (allow unknown types but log warning)
        if mime_type not in cls.ALLOWED_MIME_TYPES:
            if mime_type != 'application/octet-stream':
                # Allow unknown types but could add logging here
                pass
