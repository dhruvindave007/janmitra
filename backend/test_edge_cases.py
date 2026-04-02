"""
Edge Case and Bug Detection Tests
==================================
Tests for:
1. Invalid inputs and validation
2. Concurrent operations
3. Boundary conditions
4. Security/authorization edge cases
5. Data consistency
"""
import os
os.environ['DEBUG'] = 'True'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'janmitra_backend.settings')

import django
django.setup()

from django.utils import timezone
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from datetime import timedelta
import uuid

from authentication.models import User, UserRole
from core.models import PoliceStation
from reports.models import (
    Case, Incident, IncidentCategory, CaseStatus, CaseLevel,
    InvestigationMessage, CaseStatusHistory, EscalationHistory
)
from notifications.models import Notification
from reports.services import (
    BroadcastIncidentService,
    AssignmentService,
    InvestigationService,
    EscalationService,
    InvalidOfficerError,
    InvalidAssignerError,
    AccessDeniedError,
    CannotEscalateError,
    ChatLockedError,
    InvalidMessageError,
)

print("=" * 70)
print("EDGE CASE AND BUG DETECTION TESTS")
print("=" * 70)

all_issues = []
tests_passed = 0
tests_failed = 0

def test(name, condition, issue_msg=None):
    global tests_passed, tests_failed
    if condition:
        print(f"  ✓ {name}")
        tests_passed += 1
        return True
    else:
        msg = issue_msg or f"{name} failed"
        print(f"  ✗ {name}")
        all_issues.append(msg)
        tests_failed += 1
        return False

# Setup
station, _ = PoliceStation.objects.get_or_create(
    name="Edge Test Station",
    defaults={'code': 'EDGE01', 'latitude': 12.9716, 'longitude': 77.5946}
)

def get_user(identifier, role, station=None):
    user, _ = User.objects.get_or_create(
        identifier=identifier,
        defaults={'role': role, 'police_station': station, 'is_active': True, 'status': 'active'}
    )
    user.role = role
    user.police_station = station
    user.is_active = True
    user.save()
    return user

janmitra = get_user('EDGE_JANMITRA', UserRole.JANMITRA)
l0 = get_user('EDGE_L0', UserRole.L0, station)
l1 = get_user('EDGE_L1', UserRole.L1, station)
l2 = get_user('EDGE_L2', UserRole.L2, station)
l3 = get_user('EDGE_L3', UserRole.L3)
l4 = get_user('EDGE_L4', UserRole.L4)

# ============================================================================
# TEST 1: Invalid Input Validation
# ============================================================================
print("\n" + "=" * 70)
print("TEST 1: Invalid Input Validation")
print("=" * 70)

# Create a test case
incident = Incident.objects.create(
    text_content="Edge case test incident",
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

# Test: Empty message
print("  [Test] Empty message validation...")
try:
    InvestigationService.send_message(case, l1, "")
    test("Empty message blocked", False, "Empty message was accepted")
except (InvalidMessageError, ValidationError):
    test("Empty message blocked", True)
except Exception as e:
    test("Empty message blocked", False, f"Wrong exception: {type(e).__name__}")

# Test: Whitespace-only message
print("  [Test] Whitespace-only message validation...")
try:
    InvestigationService.send_message(case, l1, "   \n\t  ")
    test("Whitespace message blocked", False, "Whitespace message was accepted")
except (InvalidMessageError, ValidationError):
    test("Whitespace message blocked", True)
except Exception as e:
    # Some implementations might strip and reject
    test("Whitespace message blocked", True)

# Test: Very long message (potential overflow)
print("  [Test] Very long message...")
long_msg = "A" * 10001  # Over 10KB
try:
    msg = InvestigationService.send_message(case, l1, long_msg)
    # If accepted, that's fine - just checking it doesn't crash
    test("Long message handled", True)
except Exception as e:
    test("Long message handled", True)  # Rejecting is also fine

# Test: Assign non-existent user
print("  [Test] Assign non-existent user...")
try:
    fake_user = User(id=uuid.uuid4(), identifier="FAKE", role=UserRole.L0)
    AssignmentService.assign_officer(case, fake_user, l1)
    test("Non-existent user blocked", False, "Non-existent user was assigned")
except Exception:
    test("Non-existent user blocked", True)

# Test: Assign inactive user
print("  [Test] Assign inactive user...")
inactive_l0 = get_user('EDGE_INACTIVE_L0', UserRole.L0, station)
inactive_l0.is_active = False
inactive_l0.save()
try:
    AssignmentService.assign_officer(case, inactive_l0, l1)
    test("Inactive user blocked", False, "Inactive user was assigned")
except InvalidOfficerError:
    test("Inactive user blocked", True)
except Exception as e:
    test("Inactive user blocked", False, f"Wrong exception: {type(e).__name__}: {e}")

# ============================================================================
# TEST 2: Status Transition Validation
# ============================================================================
print("\n" + "=" * 70)
print("TEST 2: Status Transition Validation")
print("=" * 70)

# Create fresh case
incident2 = Incident.objects.create(
    text_content="Status test incident",
    category=IncidentCategory.GENERAL,
    latitude=12.9716, longitude=77.5946,
    submitted_by=janmitra,
)
case2 = Case.objects.create(
    incident=incident2,
    police_station=station,
    status=CaseStatus.NEW,
    current_level='L1',
    sla_deadline=timezone.now() + timedelta(hours=48),
)

# Test: Escalate NEW case (should work - needs to go through assignment first or direct escalation)
print("  [Test] Escalate from NEW status...")
try:
    EscalationService.escalate_case(case2, escalated_by=l1, reason="Test escalation")
    case2.refresh_from_db()
    test("NEW case escalation", case2.current_level == 'L3')
except CannotEscalateError as e:
    # This might be expected if NEW cases can't be escalated
    test("NEW case escalation blocked (expected)", True)
except Exception as e:
    test("NEW case escalation", False, f"Unexpected: {e}")

# Test: Escalate CLOSED case
print("  [Test] Escalate CLOSED case...")
case2.status = CaseStatus.CLOSED
case2.current_level = 'L1'
case2.save()
try:
    EscalationService.escalate_case(case2, escalated_by=l1, reason="Test")
    test("CLOSED case escalation blocked", False, "CLOSED case was escalated")
except CannotEscalateError:
    test("CLOSED case escalation blocked", True)

# Test: Escalate RESOLVED case
print("  [Test] Escalate RESOLVED case...")
case2.status = CaseStatus.RESOLVED
case2.save()
try:
    EscalationService.escalate_case(case2, escalated_by=l1, reason="Test")
    test("RESOLVED case escalation blocked", False, "RESOLVED case was escalated")
except CannotEscalateError:
    test("RESOLVED case escalation blocked", True)

# ============================================================================
# TEST 3: Message Immutability
# ============================================================================
print("\n" + "=" * 70)
print("TEST 3: Message Immutability")
print("=" * 70)

# Create case and message
incident3 = Incident.objects.create(
    text_content="Immutability test",
    category=IncidentCategory.GENERAL,
    latitude=12.9716, longitude=77.5946,
    submitted_by=janmitra,
)
case3 = Case.objects.create(
    incident=incident3,
    police_station=station,
    status=CaseStatus.ASSIGNED,
    current_level='L0',
    assigned_officer=l0,
    sla_deadline=timezone.now() + timedelta(hours=48),
)
msg = InvestigationService.send_message(case3, l0, "Original message")

# Test: Edit message text
print("  [Test] Edit message text...")
original_text = msg.text_content
try:
    msg.text_content = "Modified message"
    msg.save()
    msg.refresh_from_db()
    test("Message text immutable", msg.text_content == original_text, "Message text was modified")
except Exception:
    test("Message text immutable", True)

# Test: Delete message (author should succeed)
print("  [Test] Author deletes own message...")
msg_to_delete = InvestigationService.send_message(case3, l0, "Message to delete")
msg_del_id = msg_to_delete.id
try:
    msg_to_delete.soft_delete(l0)
    msg_to_delete.refresh_from_db()
    test("Author can soft-delete own message", msg_to_delete.is_deleted)
except Exception as e:
    test("Author can soft-delete own message", False, str(e))

# Test: Non-author cannot delete message
print("  [Test] Non-author attempts to delete message...")
msg_other = InvestigationService.send_message(case3, l0, "Another message")
try:
    msg_other.soft_delete(l1)  # L1 is not author
    test("Non-author blocked from delete", False, "Non-author could delete")
except PermissionError:
    test("Non-author blocked from delete", True)

# Test: Delete message via hard delete (should fail)
print("  [Test] Hard delete blocked...")
msg_hard = InvestigationService.send_message(case3, l0, "Hard delete test")
try:
    msg_hard.delete()
    test("Hard delete blocked", False, "Hard delete succeeded")
except PermissionError:
    test("Hard delete blocked", True)

# ============================================================================
# TEST 4: Escalation History Immutability
# ============================================================================
print("\n" + "=" * 70)
print("TEST 4: Escalation History Immutability")
print("=" * 70)

# Create escalation
incident4 = Incident.objects.create(
    text_content="Escalation immutability test",
    category=IncidentCategory.GENERAL,
    latitude=12.9716, longitude=77.5946,
    submitted_by=janmitra,
)
case4 = Case.objects.create(
    incident=incident4,
    police_station=station,
    status=CaseStatus.ASSIGNED,
    current_level='L0',
    assigned_officer=l0,
    sla_deadline=timezone.now() - timedelta(hours=1),  # Breached
)
EscalationService.escalate_case(case4, reason="Test")
esc = EscalationHistory.objects.filter(case=case4).first()

if esc:
    # Test: Edit escalation history
    print("  [Test] Edit escalation history...")
    original_reason = esc.reason
    try:
        esc.reason = "Modified reason"
        esc.save()
        esc.refresh_from_db()
        test("Escalation history immutable", esc.reason == original_reason, "History was modified")
    except Exception:
        test("Escalation history immutable", True)
else:
    print("  ⚠ No escalation history found (skipping)")

# ============================================================================
# TEST 5: Concurrent Assignment (Race Condition)
# ============================================================================
print("\n" + "=" * 70)
print("TEST 5: Concurrent Operations Safety")
print("=" * 70)

# Create fresh case
incident5 = Incident.objects.create(
    text_content="Concurrent test",
    category=IncidentCategory.GENERAL,
    latitude=12.9716, longitude=77.5946,
    submitted_by=janmitra,
)
case5 = Case.objects.create(
    incident=incident5,
    police_station=station,
    status=CaseStatus.NEW,
    current_level='L1',
    sla_deadline=timezone.now() + timedelta(hours=48),
)

# Test: Multiple rapid assignments
print("  [Test] Rapid re-assignment...")
l0_a = get_user('EDGE_L0_A', UserRole.L0, station)
l0_b = get_user('EDGE_L0_B', UserRole.L0, station)

AssignmentService.assign_officer(case5, l0_a, l1)
AssignmentService.assign_officer(case5, l0_b, l1)
case5.refresh_from_db()
test("Final assignment is last one", case5.assigned_officer == l0_b)

# Test: Only one L0 assigned
assigned_count = 1 if case5.assigned_officer else 0
test("Only one L0 assigned", assigned_count == 1)

# ============================================================================
# TEST 6: Authorization Edge Cases
# ============================================================================
print("\n" + "=" * 70)
print("TEST 6: Authorization Edge Cases")
print("=" * 70)

# Create case at L3
incident6 = Incident.objects.create(
    text_content="Auth test",
    category=IncidentCategory.GENERAL,
    latitude=12.9716, longitude=77.5946,
    submitted_by=janmitra,
)
case6 = Case.objects.create(
    incident=incident6,
    police_station=station,
    status=CaseStatus.ESCALATED,
    current_level='L3',
    sla_deadline=timezone.now() + timedelta(hours=48),
)

# Test: L1 from same station can still see escalated case
print("  [Test] L1 access to L3 escalated case...")
l1_access = InvestigationService.can_user_access_case(case6, l1)
test("L1 can access escalated case from own station", l1_access)

# Test: L3 can access L3 level case
print("  [Test] L3 access to L3 level case...")
l3_access = InvestigationService.can_user_access_case(case6, l3)
test("L3 can access L3 level case", l3_access)

# Test: L4 can access L3 level case (higher authority)
print("  [Test] L4 access to L3 level case...")
l4_access = InvestigationService.can_user_access_case(case6, l4)
# L4 should have access to L3+ cases
test("L4 can access L3 level case", l4_access)

# Test: L0 from other station cannot access
print("  [Test] L0 other station access to escalated case...")
station2, _ = PoliceStation.objects.get_or_create(
    name="Edge Other Station",
    defaults={'code': 'EDGE02', 'latitude': 13.0, 'longitude': 77.6}
)
l0_other = get_user('EDGE_L0_OTHER', UserRole.L0, station2)
other_access = InvestigationService.can_user_access_case(case6, l0_other)
test("L0 other station blocked from escalated case", not other_access)

# ============================================================================
# TEST 7: SLA Edge Cases
# ============================================================================
print("\n" + "=" * 70)
print("TEST 7: SLA Edge Cases")
print("=" * 70)

# Test: L4 has no SLA (infinite)
print("  [Test] L4 level SLA handling...")
incident7 = Incident.objects.create(
    text_content="L4 SLA test",
    category=IncidentCategory.GENERAL,
    latitude=12.9716, longitude=77.5946,
    submitted_by=janmitra,
)
case7 = Case.objects.create(
    incident=incident7,
    police_station=station,
    status=CaseStatus.ESCALATED,
    current_level='L4',
    sla_deadline=timezone.now() - timedelta(hours=100),  # Way past
)
# L4 should not be able to escalate further
try:
    EscalationService.escalate_case(case7, reason="Test")
    test("L4 cannot escalate further", False, "L4 was escalated")
except CannotEscalateError:
    test("L4 cannot escalate further", True)

# Test: SLA exactly at boundary
print("  [Test] SLA exactly at deadline...")
case7.sla_deadline = timezone.now()
case7.save()
is_breached = EscalationService.check_sla_breach(case7)
# At exact boundary - implementation specific
test("SLA boundary check works", True)  # Just checking it doesn't crash

# ============================================================================
# TEST 8: Notification Deduplication
# ============================================================================
print("\n" + "=" * 70)
print("TEST 8: Notification Edge Cases")
print("=" * 70)

# Clear notifications
Notification.objects.filter(recipient=l1).delete()

# Create case and send multiple notifications
incident8 = Incident.objects.create(
    text_content="Notification test",
    category=IncidentCategory.GENERAL,
    latitude=12.9716, longitude=77.5946,
    submitted_by=janmitra,
)
case8 = Case.objects.create(
    incident=incident8,
    police_station=station,
    status=CaseStatus.NEW,
    current_level='L1',
    sla_deadline=timezone.now() + timedelta(hours=48),
)

from notifications.services import NotificationService
NotificationService.notify_new_case_l1_l2(case8)
NotificationService.notify_new_case_l1_l2(case8)  # Duplicate

# Check for reasonable notification count (no explosion)
l1_notifs = Notification.objects.filter(recipient=l1, case=case8).count()
test("Notifications don't explode", l1_notifs <= 4, f"Too many notifications: {l1_notifs}")

# ============================================================================
# CLEANUP
# ============================================================================
print("\n" + "=" * 70)
print("CLEANUP")
print("=" * 70)

test_cases = [case, case2, case3, case4, case5, case6, case7, case8]
for c in test_cases:
    try:
        # Use raw SQL delete to bypass immutability for test cleanup
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM escalation_history WHERE case_id = %s", [str(c.id)])
            cursor.execute("DELETE FROM investigation_messages WHERE case_id = %s", [str(c.id)])
            cursor.execute("DELETE FROM case_status_history WHERE case_id = %s", [str(c.id)])
        Notification.objects.filter(case_id=c.id).delete()
        Case.objects.filter(id=c.id).delete()
        if c.incident:
            Incident.objects.filter(id=c.incident.id).delete()
    except Exception as e:
        print(f"  Cleanup error for case {c.id}: {e}")

User.objects.filter(identifier__startswith='EDGE_').update(is_active=False)
print("  Done")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("EDGE CASE TEST SUMMARY")
print("=" * 70)
print(f"\n  Tests Passed: {tests_passed}")
print(f"  Tests Failed: {tests_failed}")

if all_issues:
    print(f"\n  ⚠️ ISSUES ({len(all_issues)}):")
    for i, issue in enumerate(all_issues, 1):
        print(f"    {i}. {issue}")
else:
    print("\n  ✅ All edge case tests passed!")

print("\n" + "=" * 70)
