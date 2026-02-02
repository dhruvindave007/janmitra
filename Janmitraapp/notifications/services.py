"""
Notification service for JanMitra Backend.

Central service for creating notifications.
All notification creation should go through this service.

Usage:
    from notifications.services import NotificationService
    
    NotificationService.notify_new_case(case)
    NotificationService.notify_case_escalated(case, from_level, to_level)
    NotificationService.notify_case_solved(case)
"""

from django.db import transaction
from django.utils import timezone

from authentication.models import User, UserRole
from .models import Notification, NotificationType


class NotificationService:
    """
    Central service for creating and managing notifications.
    
    All notification logic is centralized here to:
    - Ensure consistency
    - Make it easy to add push notifications later
    - Centralize recipient selection logic
    """
    
    @classmethod
    def _get_users_by_level(cls, level):
        """Get all active authority users at a specific level."""
        role_mapping = {
            2: [UserRole.LEVEL_2, UserRole.LEVEL_2_CAPTAIN],
            1: [UserRole.LEVEL_1],
            0: [UserRole.LEVEL_0],
        }
        
        roles = role_mapping.get(level, [])
        if not roles:
            return User.objects.none()
        
        return User.objects.filter(
            role__in=roles,
            is_active=True,
            is_deleted=False
        )
    
    @classmethod
    def _get_captains(cls):
        """Get all active Level-2 Captains."""
        return User.objects.filter(
            role=UserRole.LEVEL_2_CAPTAIN,
            is_active=True,
            is_deleted=False
        )
    
    @classmethod
    def _create_notification(
        cls,
        recipient,
        title,
        message,
        notification_type=NotificationType.GENERAL,
        case=None,
        level=None
    ):
        """Create a single notification."""
        return Notification.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            case=case,
            level=level,
        )
    
    @classmethod
    def _bulk_notify(
        cls,
        recipients,
        title,
        message,
        notification_type=NotificationType.GENERAL,
        case=None,
        level=None
    ):
        """Create notifications for multiple recipients."""
        notifications = []
        for recipient in recipients:
            notifications.append(
                Notification(
                    recipient=recipient,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    case=case,
                    level=level,
                )
            )
        
        if notifications:
            Notification.objects.bulk_create(notifications)
        
        return len(notifications)
    
    # =========================================================================
    # PUBLIC API - Use these methods from views
    # =========================================================================
    
    @classmethod
    def notify_new_case(cls, case):
        """
        Notify Level-2 officers about a new case.
        
        Called when: JanMitra broadcasts an incident.
        Recipients: All Level-2 officers and captains.
        """
        level_2_users = cls._get_users_by_level(2)
        
        # Truncate incident text for title
        incident_text = case.incident.text_content[:50]
        if len(case.incident.text_content) > 50:
            incident_text += '...'
        
        title = f"New Case: {incident_text}"
        message = (
            f"A new incident has been reported.\n\n"
            f"Category: {case.incident.get_category_display()}\n"
            f"SLA Deadline: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Description: {case.incident.text_content}"
        )
        
        count = cls._bulk_notify(
            recipients=level_2_users,
            title=title,
            message=message,
            notification_type=NotificationType.NEW_CASE,
            case=case,
            level=2,
        )
        
        return count
    
    @classmethod
    def notify_case_escalated(cls, case, from_level, to_level, escalated_by=None, reason=None):
        """
        Notify officers at the new level about an escalated case.
        
        Called when: Case is forwarded/escalated.
        Recipients: All officers at the new level.
        """
        new_level_users = cls._get_users_by_level(to_level)
        
        escalator = escalated_by.identifier if escalated_by else "System"
        reason_text = reason or "No reason provided"
        
        title = f"Case Escalated to Level {to_level}"
        message = (
            f"A case has been escalated from Level {from_level} to Level {to_level}.\n\n"
            f"Escalated by: {escalator}\n"
            f"Reason: {reason_text}\n"
            f"SLA Deadline: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Description: {case.incident.text_content[:200]}"
        )
        
        count = cls._bulk_notify(
            recipients=new_level_users,
            title=title,
            message=message,
            notification_type=NotificationType.CASE_ESCALATED,
            case=case,
            level=to_level,
        )
        
        return count
    
    @classmethod
    def notify_case_solved(cls, case, solved_by):
        """
        Notify captains about a solved case.
        
        Called when: Case is marked as solved.
        Recipients: Level-2 Captains.
        """
        captains = cls._get_captains()
        
        title = f"Case Solved"
        message = (
            f"A case has been resolved.\n\n"
            f"Solved by: {solved_by.identifier}\n"
            f"Solution: {case.solution_notes or 'No notes provided'}\n\n"
            f"Original incident: {case.incident.text_content[:200]}"
        )
        
        count = cls._bulk_notify(
            recipients=captains,
            title=title,
            message=message,
            notification_type=NotificationType.CASE_SOLVED,
            case=case,
            level=case.current_level,
        )
        
        return count
    
    @classmethod
    def notify_case_rejected(cls, case, rejected_by, reason):
        """
        Notify captains about a rejected case.
        
        Called when: Case is rejected.
        Recipients: Level-2 Captains.
        """
        captains = cls._get_captains()
        
        title = f"Case Rejected"
        message = (
            f"A case has been rejected.\n\n"
            f"Rejected by: {rejected_by.identifier}\n"
            f"Reason: {reason}\n\n"
            f"Original incident: {case.incident.text_content[:200]}"
        )
        
        count = cls._bulk_notify(
            recipients=captains,
            title=title,
            message=message,
            notification_type=NotificationType.CASE_REJECTED,
            case=case,
            level=case.current_level,
        )
        
        return count
    
    @classmethod
    def notify_case_closed(cls, case, closed_by, reason=None):
        """
        Notify relevant officers about a closed case.
        
        Called when: Case is force-closed by admin.
        Recipients: Officers at the case's current level.
        """
        level_users = cls._get_users_by_level(case.current_level)
        
        title = f"Case Closed by Admin"
        message = (
            f"A case has been administratively closed.\n\n"
            f"Closed by: {closed_by.identifier}\n"
            f"Reason: {reason or 'Administrative action'}\n\n"
            f"Original incident: {case.incident.text_content[:200]}"
        )
        
        count = cls._bulk_notify(
            recipients=level_users,
            title=title,
            message=message,
            notification_type=NotificationType.CASE_CLOSED,
            case=case,
            level=case.current_level,
        )
        
        return count
    
    @classmethod
    def notify_sla_warning(cls, case, hours_remaining):
        """
        Notify officers about an approaching SLA deadline.
        
        Called when: SLA is approaching (e.g., 4 hours remaining).
        Recipients: Officers at the case's current level.
        """
        level_users = cls._get_users_by_level(case.current_level)
        
        title = f"SLA Warning: {hours_remaining}h remaining"
        message = (
            f"A case is approaching its SLA deadline.\n\n"
            f"Time remaining: {hours_remaining} hours\n"
            f"Deadline: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Description: {case.incident.text_content[:200]}"
        )
        
        count = cls._bulk_notify(
            recipients=level_users,
            title=title,
            message=message,
            notification_type=NotificationType.SLA_WARNING,
            case=case,
            level=case.current_level,
        )
        
        return count
    
    @classmethod
    def notify_sla_breached(cls, case):
        """
        Notify officers and captains about an SLA breach.
        
        Called when: SLA deadline has passed.
        Recipients: Officers at current level + all captains.
        """
        level_users = cls._get_users_by_level(case.current_level)
        captains = cls._get_captains()
        
        # Combine and deduplicate
        all_recipients = set(level_users) | set(captains)
        
        title = f"⚠️ SLA BREACHED"
        message = (
            f"A case has breached its SLA deadline!\n\n"
            f"Deadline was: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n"
            f"Current Level: {case.current_level}\n\n"
            f"Description: {case.incident.text_content[:200]}"
        )
        
        count = cls._bulk_notify(
            recipients=all_recipients,
            title=title,
            message=message,
            notification_type=NotificationType.SLA_BREACHED,
            case=case,
            level=case.current_level,
        )
        
        return count
    
    @classmethod
    def notify_auto_escalation(cls, case, from_level, to_level):
        """
        Notify officers about automatic SLA-based escalation.
        
        Called when: Case is auto-escalated due to SLA breach.
        Recipients: Officers at the new level.
        """
        new_level_users = cls._get_users_by_level(to_level)
        
        title = f"Auto-Escalated Case (SLA Breach)"
        message = (
            f"A case has been automatically escalated due to SLA breach.\n\n"
            f"Escalated from Level {from_level} to Level {to_level}\n"
            f"New SLA Deadline: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Description: {case.incident.text_content[:200]}"
        )
        
        count = cls._bulk_notify(
            recipients=new_level_users,
            title=title,
            message=message,
            notification_type=NotificationType.CASE_ESCALATED,
            case=case,
            level=to_level,
        )
        
        return count
    
    @classmethod
    def notify_admin_force_escalation(cls, case, from_level, to_level, admin_user):
        """
        Notify officers about admin force escalation.
        
        Called when: Admin force-escalates a case.
        Recipients: Officers at the new level.
        """
        new_level_users = cls._get_users_by_level(to_level)
        
        title = f"Admin Force Escalation"
        message = (
            f"A case has been force-escalated by an administrator.\n\n"
            f"Admin: {admin_user.identifier}\n"
            f"Escalated from Level {from_level} to Level {to_level}\n"
            f"New SLA Deadline: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Description: {case.incident.text_content[:200]}"
        )
        
        count = cls._bulk_notify(
            recipients=new_level_users,
            title=title,
            message=message,
            notification_type=NotificationType.ADMIN_ACTION,
            case=case,
            level=to_level,
        )
        
        return count
    
    @classmethod
    def notify_user(cls, user, title, message, notification_type=NotificationType.GENERAL, case=None):
        """
        Send a notification to a specific user.
        
        Generic method for custom notifications.
        """
        return cls._create_notification(
            recipient=user,
            title=title,
            message=message,
            notification_type=notification_type,
            case=case,
            level=None,
        )
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    @classmethod
    def get_unread_count(cls, user):
        """Get count of unread notifications for a user."""
        return Notification.objects.filter(
            recipient=user,
            is_read=False
        ).count()
    
    @classmethod
    def mark_all_read(cls, user):
        """Mark all notifications as read for a user."""
        return Notification.objects.filter(
            recipient=user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
