"""
Notification service for JanMitra Backend.

Central service for creating notifications.
All notification creation should go through this service.

Usage:
    from notifications.services import NotificationService
    
    # New workflow notifications
    NotificationService.notify_case_assigned(case, officer, assigned_by)
    NotificationService.notify_case_escalated_new(case, from_level, to_level, escalated_by)
    
    # Legacy notifications
    NotificationService.notify_new_case(case)
    NotificationService.notify_case_escalated(case, from_level, to_level)
    NotificationService.notify_case_solved(case)
"""

import logging
from typing import List, Optional
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from pathlib import Path

from authentication.models import User, UserRole
from .models import Notification, NotificationType

logger = logging.getLogger(__name__)

# Firebase Admin SDK initialization (singleton)
_firebase_app = None
_firebase_init_attempted = False


def _get_firebase_app():
    """Lazily initialize Firebase Admin SDK. Returns app or None."""
    global _firebase_app, _firebase_init_attempted
    if _firebase_init_attempted:
        return _firebase_app
    _firebase_init_attempted = True
    try:
        import firebase_admin
        from firebase_admin import credentials

        # Look for service account key in multiple locations
        key_paths = [
            Path(settings.BASE_DIR) / 'firebase-service-account.json',
            Path(settings.BASE_DIR) / 'firebase_credentials.json',
            Path(settings.BASE_DIR).parent / 'firebase-service-account.json',
        ]
        # Also check env var
        import os
        env_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if env_path:
            key_paths.insert(0, Path(env_path))

        for key_path in key_paths:
            if key_path.exists():
                cred = credentials.Certificate(str(key_path))
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info(f'[FCM] Firebase Admin initialized from {key_path}')
                return _firebase_app

        logger.warning('[FCM] No Firebase service account key found. Push notifications disabled.')
        logger.warning(f'[FCM] Searched: {[str(p) for p in key_paths]}')
        return None
    except Exception as e:
        logger.error(f'[FCM] Firebase Admin init failed: {e}')
        return None


class PushNotificationService:
    """
    Service for sending push notifications via Firebase Cloud Messaging.
    
    Requires firebase-service-account.json in the backend directory.
    Gracefully degrades if Firebase is not configured.
    """
    
    MAX_PUSH_ATTEMPTS = 3
    
    @classmethod
    def send_push(cls, notification: Notification) -> bool:
        """Send a push notification via FCM."""
        notification.push_attempts += 1
        
        device_token = cls._get_device_token(notification.recipient)
        if not device_token:
            notification.push_error = "No device token available"
            notification.save(update_fields=['push_attempts', 'push_error', 'updated_at'])
            return False
        
        app = _get_firebase_app()
        if app is None:
            notification.push_error = "Firebase not configured"
            notification.save(update_fields=['push_attempts', 'push_error', 'updated_at'])
            logger.warning(f'[FCM] Skipping push for notification {notification.id} - Firebase not configured')
            return False
        
        try:
            from firebase_admin import messaging

            # Build FCM message
            data_payload = {
                'notification_id': str(notification.id),
                'type': notification.notification_type,
                'click_action': 'FLUTTER_NOTIFICATION_CLICK',
            }
            if notification.case_id:
                data_payload['case_id'] = str(notification.case_id)

            message = messaging.Message(
                notification=messaging.Notification(
                    title=notification.title,
                    body=notification.message[:200],
                ),
                data=data_payload,
                token=device_token,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        channel_id='janmitra_high',
                        priority='high',
                        default_sound=True,
                    ),
                ),
            )

            response = messaging.send(message)
            logger.info(f'[FCM] Push sent: {response} for notification {notification.id}')
            
            notification.push_sent = True
            notification.push_sent_at = timezone.now()
            notification.push_error = None
            notification.save(update_fields=[
                'push_sent', 'push_sent_at', 'push_attempts', 'push_error', 'updated_at'
            ])
            return True
            
        except Exception as e:
            error_str = str(e)[:500]
            logger.error(f'[FCM] Push failed for notification {notification.id}: {error_str}')
            notification.push_error = error_str
            notification.save(update_fields=['push_attempts', 'push_error', 'updated_at'])
            
            # If token is invalid, clear it
            if 'UNREGISTERED' in str(e).upper() or 'INVALID' in str(e).upper():
                logger.info(f'[FCM] Clearing invalid token for user {notification.recipient_id}')
                notification.recipient.device_token = None
                notification.recipient.save(update_fields=['device_token'])
            
            return False
    
    @classmethod
    def retry_failed_pushes(cls) -> int:
        """Retry failed push notifications (batch of 100)."""
        failed = Notification.objects.filter(
            push_sent=False,
            push_attempts__lt=cls.MAX_PUSH_ATTEMPTS,
            push_attempts__gt=0
        ).select_related('recipient')[:100]
        
        success_count = 0
        for notification in failed:
            if cls.send_push(notification):
                success_count += 1
        
        return success_count
    
    @classmethod
    def _get_device_token(cls, user: User) -> Optional[str]:
        """Get device token for a user."""
        return user.device_token if hasattr(user, 'device_token') else None


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
    # NEW WORKFLOW NOTIFICATIONS
    # =========================================================================
    
    @classmethod
    def _get_users_by_new_role(cls, role: str):
        """Get all active users with a specific new workflow role."""
        return User.objects.filter(
            role=role,
            is_active=True,
            is_deleted=False,
            status='active'
        )
    
    @classmethod
    def _get_l3_for_station(cls, police_station):
        """Get L3 officers whose assigned_stations include this station."""
        return User.objects.filter(
            role=UserRole.L3,
            assigned_stations=police_station,
            is_active=True,
            is_deleted=False,
            status='active'
        )
    
    @classmethod
    def _get_station_officers(cls, police_station, roles=None):
        """Get officers at a specific police station."""
        if roles is None:
            roles = [UserRole.L0, UserRole.L1, UserRole.L2]
        
        return User.objects.filter(
            role__in=roles,
            police_station=police_station,
            is_active=True,
            is_deleted=False,
            status='active'
        )
    
    @classmethod
    def notify_case_routed(cls, case):
        """
        Notify L1 at station that a new case has been routed.
        
        Called when: Incident is submitted and routed to station.
        Recipients: L1 (PSO) at the assigned station.
        """
        if not case.police_station:
            return 0
        
        l1_officers = cls._get_station_officers(
            case.police_station, 
            roles=[UserRole.L1]
        )
        
        title = "New Case Routed to Your Station"
        message = (
            f"A new incident has been routed to your station.\n\n"
            f"Category: {case.incident.get_category_display()}\n"
            f"SLA Deadline: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Please assign an officer to investigate."
        )
        
        count = cls._bulk_notify(
            recipients=l1_officers,
            title=title,
            message=message,
            notification_type=NotificationType.NEW_CASE,
            case=case,
            level=None,
        )
        
        # Trigger push notifications
        cls._trigger_push_for_case(case, NotificationType.NEW_CASE)
        
        return count
    
    @classmethod
    def notify_case_assigned(cls, case, officer, assigned_by):
        """
        Notify L0 officer that they've been assigned a case.
        
        Called when: L1 assigns L0 to a case.
        Recipients: The assigned L0 officer.
        """
        title = "New Case Assigned to You"
        message = (
            f"You have been assigned a new case.\n\n"
            f"Assigned by: {assigned_by.identifier}\n"
            f"Category: {case.incident.get_category_display()}\n"
            f"SLA Deadline: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Description: {case.incident.text_content[:200]}"
        )
        
        notification = cls._create_notification(
            recipient=officer,
            title=title,
            message=message,
            notification_type=NotificationType.CASE_ASSIGNED,
            case=case,
            level=None,
        )
        
        # Trigger push
        PushNotificationService.send_push(notification)
        
        return notification
    
    @classmethod
    def notify_case_unassigned(cls, case, officer, unassigned_by, reason=''):
        """
        Notify L0 officer that they've been removed from a case.
        
        Called when: L1 unassigns L0 from a case.
        Recipients: The unassigned L0 officer.
        """
        title = "Case Assignment Removed"
        message = (
            f"You have been unassigned from a case.\n\n"
            f"Unassigned by: {unassigned_by.identifier}\n"
            f"Reason: {reason or 'No reason provided'}\n\n"
            f"Case: {case.incident.text_content[:100]}"
        )
        
        return cls._create_notification(
            recipient=officer,
            title=title,
            message=message,
            notification_type=NotificationType.CASE_UNASSIGNED,
            case=case,
            level=None,
        )
    
    @classmethod
    def notify_case_escalated_new(cls, case, from_level, to_level, escalated_by=None, reason=''):
        """
        Notify officers at new level about escalation (new workflow).
        
        Called when: Case is escalated from station to L3, or L3 to L4.
        Recipients:
        - L3: Only L3 officers whose assigned_stations include case's station
        - L4: All L4 officers (full access)
        """
        if to_level == 'L3':
            recipients = cls._get_l3_for_station(case.police_station) if case.police_station else User.objects.none()
        elif to_level == 'L4':
            recipients = cls._get_users_by_new_role(UserRole.L4)
        else:
            return 0
        
        escalator = escalated_by.identifier if escalated_by else "System (SLA Breach)"
        
        title = f"Case Escalated to {to_level}"
        message = (
            f"A case has been escalated to your level.\n\n"
            f"From: {from_level}\n"
            f"To: {to_level}\n"
            f"Escalated by: {escalator}\n"
            f"Reason: {reason or 'SLA breach'}\n"
            f"New SLA Deadline: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Description: {case.incident.text_content[:200]}"
        )
        
        count = cls._bulk_notify(
            recipients=recipients,
            title=title,
            message=message,
            notification_type=NotificationType.CASE_ESCALATED,
            case=case,
            level=None,
        )
        
        cls._trigger_push_for_case(case, NotificationType.CASE_ESCALATED)
        
        return count
    
    @classmethod
    def notify_chat_message(cls, case, message, sender):
        """
        Notify relevant users about a new chat message.
        
        Called when: New investigation message is sent.
        Recipients: Other officers with access to the case.
        """
        # Get all users who should be notified
        recipients = []
        
        # L0 assigned officer (if not sender)
        if case.assigned_officer and case.assigned_officer != sender:
            recipients.append(case.assigned_officer)
        
        # L1/L2 at station (if not sender)
        if case.police_station:
            station_officers = cls._get_station_officers(
                case.police_station,
                roles=[UserRole.L1, UserRole.L2]
            ).exclude(id=sender.id)
            recipients.extend(station_officers)
        
        # L3 if escalated (only L3 with this station in their assigned_stations)
        if case.current_level in ['L3', 'L4'] and case.police_station:
            l3_users = cls._get_l3_for_station(case.police_station).exclude(id=sender.id)
            recipients.extend(l3_users)
        
        # L4 if at L4 level (full access)
        if case.current_level == 'L4':
            l4_users = cls._get_users_by_new_role(UserRole.L4).exclude(id=sender.id)
            recipients.extend(l4_users)
        
        # Deduplicate
        recipients = list(set(recipients))
        
        if not recipients:
            return 0
        
        sender_display = sender.identifier if sender else "System"
        preview = message.text_content[:50] if message.text_content else "[Media]"
        
        title = f"New Message from {sender_display}"
        msg_text = (
            f"New message in case investigation.\n\n"
            f"From: {sender_display}\n"
            f"Preview: {preview}"
        )
        
        return cls._bulk_notify(
            recipients=recipients,
            title=title,
            message=msg_text,
            notification_type=NotificationType.CHAT_MESSAGE,
            case=case,
            level=None,
        )
    
    @classmethod
    def notify_sla_warning_new(cls, case, hours_remaining):
        """
        Notify relevant officers about approaching SLA (new workflow).
        
        Recipients depend on current level:
        - L0/L1/L2: Station officers
        - L3: L3 users
        - L4: No notification (no SLA)
        """
        recipients = []
        
        if case.current_level in ['L0', 'L1', 'L2']:
            if case.assigned_officer:
                recipients.append(case.assigned_officer)
            if case.police_station:
                l1_officers = cls._get_station_officers(
                    case.police_station,
                    roles=[UserRole.L1]
                )
                recipients.extend(l1_officers)
        elif case.current_level == 'L3':
            if case.police_station:
                recipients.extend(cls._get_l3_for_station(case.police_station))
        
        recipients = list(set(recipients))
        
        if not recipients:
            return 0
        
        title = f"⚠️ SLA Warning: {hours_remaining}h remaining"
        message = (
            f"A case is approaching its SLA deadline.\n\n"
            f"Time remaining: {hours_remaining} hours\n"
            f"Deadline: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n"
            f"Current Level: {case.current_level}\n\n"
            f"Please take action to avoid escalation."
        )
        
        count = cls._bulk_notify(
            recipients=recipients,
            title=title,
            message=message,
            notification_type=NotificationType.SLA_WARNING,
            case=case,
            level=None,
        )
        
        cls._trigger_push_for_case(case, NotificationType.SLA_WARNING)
        
        return count
    
    @classmethod
    def notify_sla_breached_new(cls, case):
        """
        Notify about SLA breach (new workflow).
        
        Recipients: Current level officers + next level officers.
        """
        recipients = []
        
        if case.current_level in ['L0', 'L1', 'L2']:
            # Station officers + L3 for this station (next level)
            if case.police_station:
                station_officers = cls._get_station_officers(case.police_station)
                recipients.extend(station_officers)
                recipients.extend(cls._get_l3_for_station(case.police_station))
        elif case.current_level == 'L3':
            # L3 for this station + all L4
            if case.police_station:
                recipients.extend(cls._get_l3_for_station(case.police_station))
            recipients.extend(cls._get_users_by_new_role(UserRole.L4))
        
        recipients = list(set(recipients))
        
        if not recipients:
            return 0
        
        title = "⚠️ SLA BREACHED - Case Escalating"
        message = (
            f"A case has breached its SLA deadline!\n\n"
            f"Deadline was: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n"
            f"Level: {case.current_level}\n\n"
            f"The case will be automatically escalated."
        )
        
        count = cls._bulk_notify(
            recipients=recipients,
            title=title,
            message=message,
            notification_type=NotificationType.SLA_BREACHED,
            case=case,
            level=None,
        )
        
        cls._trigger_push_for_case(case, NotificationType.SLA_BREACHED)
        
        return count
    
    @classmethod
    def notify_case_solved_new(cls, case, solved_by):
        """
        Notify L2 (PI) that case needs closure (new workflow).
        
        Called when: L0 marks case as solved.
        Recipients: L2 at the station.
        """
        if not case.police_station:
            return 0
        
        l2_officers = cls._get_station_officers(
            case.police_station,
            roles=[UserRole.L2]
        )
        
        title = "Case Solved - Pending Closure"
        message = (
            f"A case has been marked as solved.\n\n"
            f"Solved by: {solved_by.identifier}\n"
            f"Solution: {case.solution_notes[:200] if case.solution_notes else 'No notes'}\n\n"
            f"Please review and close the case."
        )
        
        return cls._bulk_notify(
            recipients=l2_officers,
            title=title,
            message=message,
            notification_type=NotificationType.CASE_SOLVED,
            case=case,
            level=None,
        )
    
    @classmethod
    def notify_case_closed_new(cls, case, closed_by):
        """
        Notify relevant officers that case has been closed (new workflow).
        
        Called when: L2 closes a solved case.
        Recipients: Assigned L0 officer.
        """
        if not case.assigned_officer:
            return 0
        
        title = "Case Closed"
        message = (
            f"Your case has been closed.\n\n"
            f"Closed by: {closed_by.identifier}\n"
            f"Status: {case.status}\n\n"
            f"Thank you for your work on this case."
        )
        
        return cls._create_notification(
            recipient=case.assigned_officer,
            title=title,
            message=message,
            notification_type=NotificationType.CASE_CLOSED,
            case=case,
            level=None,
        )
    
    @classmethod
    def notify_new_case_l1_l2(cls, case):
        """
        Notify L1 and L2 officers at the police station about a new case.
        
        Called when: Citizen submits an incident and case is created.
        Recipients: L1 (PSO) and L2 (PI) at the assigned police station only.
        """
        if not case.police_station:
            return 0
        
        recipients = cls._get_station_officers(
            case.police_station,
            roles=[UserRole.L1, UserRole.L2]
        )
        
        if not recipients:
            return 0
        
        title = "New Case Created"
        message = (
            f"A new incident has been reported to your station.\n\n"
            f"Category: {case.incident.get_category_display()}\n"
            f"SLA Deadline: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Description: {case.incident.text_content[:200]}"
        )
        
        count = cls._bulk_notify(
            recipients=recipients,
            title=title,
            message=message,
            notification_type=NotificationType.NEW_CASE,
            case=case,
            level=None,
        )
        
        cls._trigger_push_for_case(case, NotificationType.NEW_CASE)
        
        return count
    
    @classmethod
    def _trigger_push_for_case(cls, case, notification_type):
        """
        Trigger push notifications for recent notifications on a case.
        
        Called after bulk creating notifications to send pushes.
        """
        recent_notifications = Notification.objects.filter(
            case=case,
            notification_type=notification_type,
            push_sent=False,
            push_attempts=0,
            created_at__gte=timezone.now() - timezone.timedelta(minutes=1)
        ).select_related('recipient')[:50]
        
        for notification in recent_notifications:
            PushNotificationService.send_push(notification)
    
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
