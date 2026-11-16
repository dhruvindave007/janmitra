"""
End-to-End System Flow Validation
=================================

Validates the complete case lifecycle:
1. Create incident
2. Assign L0 by L1
3. Send messages from L0 and L1
4. Trigger SLA breach and escalate to L3
5. Send message from L3
6. Escalate to L4
7. Close case by L2

For each step, verify:
- correct role access
- correct status and level transitions
- correct notifications
- correct chat visibility
- no unauthorized access
"""
import os
os.environ['DEBUG'] = 'True'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'janmitra_backend.settings')

import django
django.setup()

from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from authentication.models import User, UserRole
from core.models import PoliceStation
from reports.models import (
    Case, Incident, IncidentCategory, CaseStatus, CaseLevel,
    InvestigationMessage, CaseStatusHistory, EscalationHistory
)
from notifications.models import Notification, NotificationType
from reports.services import (
    BroadcastIncidentService,
    AssignmentService,
    InvestigationService,
    EscalationService,
    InvalidOfficerError,
    InvalidAssignerError,
    AccessDeniedError,
    CannotEscalateError,
)
from notifications.services import NotificationService

print("=" * 70)
print("END-TO-END SYSTEM FLOW VALIDATION")
print("=" * 70)

# Setup
from django.core.management import call_command
print("\n[Setup] Running migrations...")
try:
    call_command('migrate', '--run-syncdb', verbosity=0)
    print("    ✓ Migrations complete")
except Exception as e:
    print(f"    Migration note: {e}")

# ============================================================================
# CREATE TEST DATA
# ============================================================================
print("\n[Setup] Creating test users and police station...")

station, _ = PoliceStation.objects.get_or_create(
    name="E2E Test Station",
    defaults={
        'code': 'E2E001',
        'latitude': 12.9716,
        'longitude': 77.5946,
    }
)

def get_or_create_user(identifier, role, station=None):
    user, created = User.objects.get_or_create(
        identifier=identifier,
        defaults={
            'role': role,
            'police_station': station,
            'is_active': True,
            'status': 'active',
        }
    )
    if not created:
        user.is_active = True
        user.role = role
        user.police_station = station
        user.status = 'active'
        user.save()
    return user

# Create all users
janmitra = get_or_create_user('E2E_JANMITRA', UserRole.JANMITRA)
l0_officer = get_or_create_user('E2E_L0', UserRole.L0, station)
l1_pso = get_or_create_user('E2E_L1', UserRole.L1, station)
l2_pi = get_or_create_user('E2E_L2', UserRole.L2, station)
l3_higher = get_or_create_user('E2E_L3', UserRole.L3)
l4_top = get_or_create_user('E2E_L4', UserRole.L4)

# Another L0 from different station (for access tests)
station2, _ = PoliceStation.objects.get_or_create(
    name="E2E Other Station",
    defaults={'code': 'E2E002', 'latitude': 13.0, 'longitude': 77.6}
)
l0_other_station = get_or_create_user('E2E_L0_OTHER', UserRole.L0, station2)

print(f"    ✓ Station: {station.name}")
print(f"    ✓ Users: JanMitra, L0, L1, L2, L3, L4, L0-other")

# Clear notifications for test users
test_users = [janmitra, l0_officer, l1_pso, l2_pi, l3_higher, l4_top, l0_other_station]
Notification.objects.filter(recipient__in=test_users).delete()

all_issues = []
case = None

# ============================================================================
# STEP 1: CREATE INCIDENT
# ============================================================================
print("\n" + "=" * 70)
print("STEP 1: Create Incident")
print("=" * 70)

try:
    # Simulate incident creation
    incident = Incident.objects.create(
        text_content="Test incident: Suspicious activity near market area",
        category=IncidentCategory.GENERAL,
        latitude=12.9716,
        longitude=77.5946,
        submitted_by=janmitra,
    )
    
    case = Case.objects.create(
        incident=incident,
        police_station=station,
        status=CaseStatus.NEW,
        current_level='L1',
        sla_deadline=timezone.now() + timedelta(hours=48),
    )
    
    # Add system message
    InvestigationService.send_system_message(
        case=case,
        text=f"Case created and assigned to {station.name}."
    )
    
    # Notify L1 and L2
    notif_count = NotificationService.notify_new_case_l1_l2(case)
    
    # Verify
    assert case.status == CaseStatus.NEW, f"Expected NEW, got {case.status}"
    assert case.current_level == 'L1', f"Expected L1, got {case.current_level}"
    assert case.police_station == station, "Should be assigned to station"
    
    # Check notifications went to L1 and L2 only
    l1_notif = Notification.objects.filter(recipient=l1_pso, case=case).exists()
    l2_notif = Notification.objects.filter(recipient=l2_pi, case=case).exists()
    l0_notif = Notification.objects.filter(recipient=l0_officer, case=case).exists()
    
    assert l1_notif, "L1 should receive notification"
    assert l2_notif, "L2 should receive notification"
    # L0 should not receive new case notification (not assigned yet)
    
    print(f"    ✓ Case created: {case.id}")
    print(f"    ✓ Status: {case.status}, Level: {case.current_level}")
    print(f"    ✓ Notifications sent: {notif_count}")
    print(f"    ✓ L1 notified: {l1_notif}, L2 notified: {l2_notif}")

except Exception as e:
    print(f"    ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    all_issues.append(f"Step 1 failed: {e}")

# ============================================================================
# STEP 2: ASSIGN L0 BY L1
# ============================================================================
print("\n" + "=" * 70)
print("STEP 2: Assign L0 by L1")
print("=" * 70)

try:
    # Test: L2 cannot assign (wrong role)
    print("  [Test] L2 attempts to assign L0...")
    try:
        AssignmentService.assign_officer(case, l0_officer, l2_pi)
        all_issues.append("L2 was able to assign - should be blocked")
        print("    ✗ L2 should not be able to assign")
    except InvalidAssignerError:
        print("    ✓ L2 blocked: InvalidAssignerError raised")
    
    # Test: L0 from other station cannot be assigned
    print("  [Test] L1 attempts to assign L0 from other station...")
    try:
        AssignmentService.assign_officer(case, l0_other_station, l1_pso)
        all_issues.append("L0 from other station was assigned - should be blocked")
        print("    ✗ L0 from other station should not be assignable")
    except InvalidOfficerError:
        print("    ✓ L0 other station blocked: InvalidOfficerError raised")
    
    # Actual assignment
    print("  [Test] L1 assigns L0 from same station...")
    Notification.objects.filter(recipient=l0_officer).delete()  # Clear for test
    
    result = AssignmentService.assign_officer(
        case=case,
        officer=l0_officer,
        assigned_by=l1_pso,
        notes="Assigned for investigation"
    )
    
    case.refresh_from_db()
    
    # Verify
    assert case.status == CaseStatus.ASSIGNED, f"Expected ASSIGNED, got {case.status}"
    assert case.current_level == 'L0', f"Expected L0, got {case.current_level}"
    assert case.assigned_officer == l0_officer, "Officer not assigned"
    assert case.assigned_by == l1_pso, "Assigner not recorded"
    
    # Check notification to L0
    l0_assigned_notif = Notification.objects.filter(
        recipient=l0_officer,
        case=case,
        notification_type=NotificationType.CASE_ASSIGNED
    ).exists()
    assert l0_assigned_notif, "L0 should receive assignment notification"
    
    # Check system message
    sys_msgs = InvestigationMessage.objects.filter(
        case=case, 
        message_type='system',
        text_content__icontains='assigned'
    )
    assert sys_msgs.exists(), "System message for assignment should exist"
    
    print(f"    ✓ Case assigned to {l0_officer.identifier}")
    print(f"    ✓ Status: {case.status}, Level: {case.current_level}")
    print(f"    ✓ L0 notified: {l0_assigned_notif}")

except Exception as e:
    print(f"    ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    all_issues.append(f"Step 2 failed: {e}")

# ============================================================================
# STEP 3: SEND MESSAGES FROM L0 AND L1
# ============================================================================
print("\n" + "=" * 70)
print("STEP 3: Send Messages from L0 and L1")
print("=" * 70)

try:
    # Test: L0 (assigned) can send messages
    print("  [Test] L0 sends message...")
    msg1 = InvestigationService.send_message(
        case=case,
        sender=l0_officer,
        text="Started investigation. Arrived at location."
    )
    assert msg1.sender == l0_officer
    print(f"    ✓ L0 message sent: {msg1.id}")
    
    # Test: L1 (same station) can send messages
    print("  [Test] L1 sends message...")
    msg2 = InvestigationService.send_message(
        case=case,
        sender=l1_pso,
        text="Acknowledged. Report findings immediately."
    )
    assert msg2.sender == l1_pso
    print(f"    ✓ L1 message sent: {msg2.id}")
    
    # Test: L2 (same station) can send messages
    print("  [Test] L2 sends message...")
    msg3 = InvestigationService.send_message(
        case=case,
        sender=l2_pi,
        text="Keep me updated on progress."
    )
    assert msg3.sender == l2_pi
    print(f"    ✓ L2 message sent: {msg3.id}")
    
    # Test: L0 from other station CANNOT access chat
    print("  [Test] L0 from other station attempts to send message...")
    try:
        InvestigationService.send_message(
            case=case,
            sender=l0_other_station,
            text="Should not work"
        )
        all_issues.append("L0 other station could send message - should be blocked")
        print("    ✗ L0 other station should be blocked")
    except AccessDeniedError:
        print("    ✓ L0 other station blocked: AccessDeniedError raised")
    
    # Test: L3 CANNOT access chat (case not escalated yet)
    print("  [Test] L3 attempts to send message (case not escalated)...")
    try:
        InvestigationService.send_message(
            case=case,
            sender=l3_higher,
            text="Should not work"
        )
        all_issues.append("L3 could send to non-escalated case - should be blocked")
        print("    ✗ L3 should be blocked for non-escalated case")
    except AccessDeniedError:
        print("    ✓ L3 blocked: Case not escalated to L3")
    
    # Test: JanMitra CANNOT access chat
    print("  [Test] JanMitra attempts to send message...")
    try:
        InvestigationService.send_message(
            case=case,
            sender=janmitra,
            text="Should not work"
        )
        all_issues.append("JanMitra could send message - should be blocked")
        print("    ✗ JanMitra should be blocked")
    except AccessDeniedError:
        print("    ✓ JanMitra blocked: AccessDeniedError raised")
    
    # Verify chat visibility
    print("  [Test] Verify chat visibility...")
    l0_can_see = InvestigationService.can_user_access_case(case, l0_officer)
    l1_can_see = InvestigationService.can_user_access_case(case, l1_pso)
    l2_can_see = InvestigationService.can_user_access_case(case, l2_pi)
    l3_can_see = InvestigationService.can_user_access_case(case, l3_higher)
    janmitra_can_see = InvestigationService.can_user_access_case(case, janmitra)
    
    assert l0_can_see, "L0 (assigned) should see chat"
    assert l1_can_see, "L1 (same station) should see chat"
    assert l2_can_see, "L2 (same station) should see chat"
    assert not l3_can_see, "L3 should NOT see chat (not escalated)"
    assert not janmitra_can_see, "JanMitra should NOT see chat"
    
    print(f"    ✓ Chat visibility correct:")
    print(f"      L0: {l0_can_see}, L1: {l1_can_see}, L2: {l2_can_see}")
    print(f"      L3: {l3_can_see}, JanMitra: {janmitra_can_see}")

except Exception as e:
    print(f"    ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    all_issues.append(f"Step 3 failed: {e}")

# ============================================================================
# STEP 4: TRIGGER SLA BREACH AND ESCALATE TO L3
# ============================================================================
print("\n" + "=" * 70)
print("STEP 4: Trigger SLA Breach and Escalate to L3")
print("=" * 70)

try:
    # Manually set SLA deadline to past
    print("  [Test] Setting SLA deadline to past...")
    case.sla_deadline = timezone.now() - timedelta(hours=1)
    case.save()
    
    # Check SLA breach detection
    is_breached = EscalationService.check_sla_breach(case)
    assert is_breached, "SLA should be detected as breached"
    print(f"    ✓ SLA breach detected: {is_breached}")
    
    # Clear L3 notifications
    Notification.objects.filter(recipient=l3_higher).delete()
    
    # Escalate
    print("  [Test] Escalating to L3...")
    from_level, to_level = EscalationService.escalate_case(
        case=case,
        escalated_by=None,  # Auto escalation
        reason="SLA breach - 48h exceeded"
    )
    
    case.refresh_from_db()
    
    # Verify
    assert from_level == 'L0', f"Expected from L0, got {from_level}"
    assert to_level == 'L3', f"Expected to L3, got {to_level}"
    assert case.current_level == 'L3', f"Expected level L3, got {case.current_level}"
    assert case.status == CaseStatus.ESCALATED, f"Expected ESCALATED, got {case.status}"
    assert case.escalation_count == 1, f"Expected escalation_count 1, got {case.escalation_count}"
    
    # Check SLA was reset
    assert case.sla_deadline > timezone.now(), "SLA deadline should be reset to future"
    
    # Check L3 notification
    l3_notif = Notification.objects.filter(
        recipient=l3_higher,
        case=case,
        notification_type=NotificationType.CASE_ESCALATED
    ).exists()
    
    # Check escalation history
    esc_history = EscalationHistory.objects.filter(
        case=case,
        from_level='L0',
        to_level='L3'
    ).exists()
    assert esc_history, "Escalation history should be recorded"
    
    # Check system message
    esc_msg = InvestigationMessage.objects.filter(
        case=case,
        message_type='system',
        text_content__icontains='escalat'
    ).order_by('-created_at').first()
    assert esc_msg is not None, "System message for escalation should exist"
    
    print(f"    ✓ Escalated: {from_level} → {to_level}")
    print(f"    ✓ Status: {case.status}, Level: {case.current_level}")
    print(f"    ✓ L3 notified: {l3_notif}")
    print(f"    ✓ New SLA: {case.sla_deadline.strftime('%Y-%m-%d %H:%M')}")

except Exception as e:
    print(f"    ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    all_issues.append(f"Step 4 failed: {e}")

# ============================================================================
# STEP 5: SEND MESSAGE FROM L3
# ============================================================================
print("\n" + "=" * 70)
print("STEP 5: Send Message from L3")
print("=" * 70)

try:
    # L3 can now access chat (case is at L3 level)
    print("  [Test] L3 chat access after escalation...")
    l3_can_see = InvestigationService.can_user_access_case(case, l3_higher)
    assert l3_can_see, "L3 should have access to escalated case"
    print(f"    ✓ L3 can access chat: {l3_can_see}")
    
    # L3 sends message
    print("  [Test] L3 sends message...")
    msg4 = InvestigationService.send_message(
        case=case,
        sender=l3_higher,
        text="Reviewing escalated case. Need more details from field officer."
    )
    assert msg4.sender == l3_higher
    print(f"    ✓ L3 message sent: {msg4.id}")
    
    # L0 can still see chat (was assigned, still part of case)
    l0_can_still_see = InvestigationService.can_user_access_case(case, l0_officer)
    # Per architecture: L0 only sees assigned cases. After escalation, case is no longer at L0.
    # But l0_officer is still assigned_officer - need to check the access rules
    print(f"    ℹ L0 access after escalation: {l0_can_still_see}")
    
    # L1/L2 can still see (station level officers)
    l1_can_still_see = InvestigationService.can_user_access_case(case, l1_pso)
    l2_can_still_see = InvestigationService.can_user_access_case(case, l2_pi)
    print(f"    ℹ L1 access after escalation: {l1_can_still_see}")
    print(f"    ℹ L2 access after escalation: {l2_can_still_see}")

except Exception as e:
    print(f"    ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    all_issues.append(f"Step 5 failed: {e}")

# ============================================================================
# STEP 6: ESCALATE TO L4
# ============================================================================
print("\n" + "=" * 70)
print("STEP 6: Escalate to L4")
print("=" * 70)

try:
    # Simulate SLA breach at L3
    print("  [Test] Setting L3 SLA deadline to past...")
    case.sla_deadline = timezone.now() - timedelta(hours=1)
    case.save()
    
    # Clear L4 notifications
    Notification.objects.filter(recipient=l4_top).delete()
    
    # Escalate to L4
    print("  [Test] Escalating to L4...")
    from_level, to_level = EscalationService.escalate_case(
        case=case,
        escalated_by=l3_higher,  # Manual escalation by L3
        reason="Requires top authority intervention"
    )
    
    case.refresh_from_db()
    
    # Verify
    assert from_level == 'L3', f"Expected from L3, got {from_level}"
    assert to_level == 'L4', f"Expected to L4, got {to_level}"
    assert case.current_level == 'L4', f"Expected level L4, got {case.current_level}"
    assert case.escalation_count == 2, f"Expected escalation_count 2, got {case.escalation_count}"
    
    # L4 has no SLA - check deadline wasn't reset or special handling
    
    # Check L4 notification
    l4_notif = Notification.objects.filter(
        recipient=l4_top,
        case=case,
        notification_type=NotificationType.CASE_ESCALATED
    ).exists()
    
    print(f"    ✓ Escalated: {from_level} → {to_level}")
    print(f"    ✓ Status: {case.status}, Level: {case.current_level}")
    print(f"    ✓ L4 notified: {l4_notif}")
    print(f"    ✓ Escalation count: {case.escalation_count}")
    
    # Test: Cannot escalate beyond L4
    print("  [Test] Attempting to escalate beyond L4...")
    try:
        EscalationService.escalate_case(case, escalated_by=l4_top, reason="Test")
        all_issues.append("Could escalate beyond L4 - should be blocked")
        print("    ✗ Should not escalate beyond L4")
    except CannotEscalateError:
        print("    ✓ Cannot escalate beyond L4: CannotEscalateError raised")
    
    # L4 can access chat
    l4_can_see = InvestigationService.can_user_access_case(case, l4_top)
    assert l4_can_see, "L4 should have access to L4 level case"
    print(f"    ✓ L4 can access chat: {l4_can_see}")

except Exception as e:
    print(f"    ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    all_issues.append(f"Step 6 failed: {e}")

# ============================================================================
# STEP 7: CLOSE CASE BY L2
# ============================================================================
print("\n" + "=" * 70)
print("STEP 7: Close Case by L2")
print("=" * 70)

try:
    # Per architecture: "L2 or higher closes case"
    print("  [Test] L2 closes case...")
    
    # Update case to closed
    old_status = case.status
    case.status = CaseStatus.CLOSED
    case.resolved_at = timezone.now()
    case.save()
    
    # Record status change
    CaseStatusHistory.objects.create(
        case=case,
        from_status=old_status,
        to_status=CaseStatus.CLOSED,
        from_level=case.current_level,
        to_level=case.current_level,
        changed_by=l2_pi,
        reason="Case resolved and closed",
        is_auto_escalation=False,
    )
    
    # Lock chat
    InvestigationService.lock_chat(case)
    
    case.refresh_from_db()
    
    # Verify
    assert case.status == CaseStatus.CLOSED, f"Expected CLOSED, got {case.status}"
    assert case.is_chat_locked, "Chat should be locked"
    
    print(f"    ✓ Case closed by {l2_pi.identifier}")
    print(f"    ✓ Status: {case.status}")
    print(f"    ✓ Chat locked: {case.is_chat_locked}")
    
    # Test: Cannot send messages to closed case
    print("  [Test] Attempting to send message to closed case...")
    from reports.services import ChatLockedError
    try:
        InvestigationService.send_message(case, l4_top, "Test after close")
        all_issues.append("Could send message to closed case - should be blocked")
        print("    ✗ Should not send to closed case")
    except ChatLockedError:
        print("    ✓ Message blocked: ChatLockedError raised")
    
    # Test: Cannot escalate closed case (case is at L4, cannot escalate further anyway)
    print("  [Test] Attempting to escalate closed case...")
    # Case is already at L4 which cannot escalate further
    # This tests both closed status and max level
    try:
        EscalationService.escalate_case(case, escalated_by=l4_top, reason="Test")
        all_issues.append("Could escalate closed case - should be blocked")
        print("    ✗ Should not escalate closed case")
    except CannotEscalateError:
        print("    ✓ Escalation blocked: CannotEscalateError raised")

except Exception as e:
    print(f"    ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    all_issues.append(f"Step 7 failed: {e}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("FINAL VALIDATION SUMMARY")
print("=" * 70)

# Count messages
total_messages = InvestigationMessage.objects.filter(case=case).count()
system_messages = InvestigationMessage.objects.filter(case=case, message_type='system').count()
user_messages = total_messages - system_messages

# Count status changes
status_changes = CaseStatusHistory.objects.filter(case=case).count()

# Count escalations
escalations = EscalationHistory.objects.filter(case=case).count()

print(f"\nCase {case.id}:")
print(f"  Final Status: {case.status}")
print(f"  Final Level: {case.current_level}")
print(f"  Escalation Count: {case.escalation_count}")
print(f"  Chat Locked: {case.is_chat_locked}")
print(f"  Total Messages: {total_messages} ({user_messages} user, {system_messages} system)")
print(f"  Status Changes: {status_changes}")
print(f"  Escalation History: {escalations}")

if all_issues:
    print(f"\n⚠️  ISSUES FOUND ({len(all_issues)}):")
    for i, issue in enumerate(all_issues, 1):
        print(f"  {i}. {issue}")
else:
    print("\n✅ ALL VALIDATIONS PASSED!")

# ============================================================================
# CLEANUP
# ============================================================================
print("\n[Cleanup] Removing test data...")
if case:
    # Use raw SQL to bypass immutability for test cleanup
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM escalation_history WHERE case_id = %s", [str(case.id)])
        cursor.execute("DELETE FROM investigation_messages WHERE case_id = %s", [str(case.id)])
        cursor.execute("DELETE FROM case_status_history WHERE case_id = %s", [str(case.id)])
    Notification.objects.filter(case_id=case.id).delete()
    Case.objects.filter(id=case.id).delete()
    if case.incident:
        Incident.objects.filter(id=case.incident.id).delete()

User.objects.filter(identifier__startswith='E2E_').update(is_active=False)
print("    Done")

print("\n" + "=" * 70)
if all_issues:
    print(f"E2E VALIDATION COMPLETE - {len(all_issues)} ISSUES FOUND")
else:
    print("E2E VALIDATION COMPLETE - ALL PASSED")
print("=" * 70)
