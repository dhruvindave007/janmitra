"""Tests for the audit trail: API, immutability, and what gets recorded."""

import hashlib

from django.test import RequestFactory, TestCase

from audit.models import AuditEventType, AuditLog, IdentityRevealLog
from authentication.models import UserRole
from core.testing import client_for, make_station, make_user

LOGS = '/api/v1/audit/logs/'


class AuditApiTests(TestCase):
    """
    Regression: every audit endpoint raised FieldError (HTTP 500). The
    serializers, filters and querysets referenced columns and relations
    (created_at, action, actor, resource_type) that AuditLog never had.
    """

    @classmethod
    def setUpTestData(cls):
        cls.supervisor = make_user(UserRole.L1, station=make_station())
        cls.inspector = make_user(UserRole.L2, station=make_station())
        cls.login = AuditLog.log(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            actor=cls.supervisor,
            description='Authority login successful',
        )
        cls.failed = AuditLog.log(
            event_type=AuditEventType.AUTH_LOGIN_FAILED,
            success=False,
            description='Invalid identifier',
        )

    def test_list_returns_stored_columns_newest_first(self):
        response = client_for(self.supervisor).get(LOGS)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 2)
        first = response.data['results'][0]
        self.assertEqual(first['id'], str(self.failed.id))
        self.assertEqual(first['event_type'], AuditEventType.AUTH_LOGIN_FAILED)
        self.assertFalse(first['success'])

    def test_actor_is_reported_from_denormalised_columns(self):
        response = client_for(self.supervisor).get(f'{LOGS}{self.login.id}/')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['actor_id'], str(self.supervisor.id))
        self.assertEqual(response.data['actor_role'], UserRole.L1)
        self.assertEqual(response.data['actor_identifier'], self.supervisor.identifier)

    def test_filters(self):
        client = client_for(self.supervisor)

        by_type = client.get(LOGS, {'event_type': AuditEventType.AUTH_LOGIN_FAILED})
        by_actor = client.get(LOGS, {'actor_id': str(self.supervisor.id)})
        by_success = client.get(LOGS, {'success': 'false'})

        self.assertEqual([r['id'] for r in by_type.data['results']], [str(self.failed.id)])
        self.assertEqual([r['id'] for r in by_actor.data['results']], [str(self.login.id)])
        self.assertEqual([r['id'] for r in by_success.data['results']], [str(self.failed.id)])

    def test_stats(self):
        response = client_for(self.supervisor).get(f'{LOGS}stats/')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['total_audit_logs'], 2)
        self.assertEqual(response.data['total_failed_events'], 1)
        self.assertEqual(response.data['activity']['last_24_hours'], 2)
        self.assertEqual(len(response.data['event_types_breakdown']), 2)

    def test_identity_reveal_logs(self):
        entry = IdentityRevealLog.objects.create(
            janmitra_user_id='a' * 36,
            revealed_to_user_id=str(self.supervisor.id),
            revealed_to_role=UserRole.L1,
            approved_by_user_id=str(self.supervisor.id),
            justification='Court order',
        )
        client = client_for(self.supervisor)

        listing = client.get('/api/v1/audit/identity-reveals/')
        detail = client.get(f'/api/v1/audit/identity-reveals/{entry.id}/')

        self.assertEqual(listing.status_code, 200, listing.data)
        self.assertEqual(listing.data['count'], 1)
        self.assertEqual(detail.data['justification'], 'Court order')

    def test_access_is_restricted(self):
        for user in (self.inspector, make_user(UserRole.L0), make_user(UserRole.JANMITRA)):
            with self.subTest(role=user.role):
                self.assertEqual(client_for(user).get(LOGS).status_code, 403)
        self.assertEqual(client_for().get(LOGS).status_code, 401)

    def test_api_is_read_only(self):
        client = client_for(self.supervisor)

        self.assertEqual(client.post(LOGS, {}, format='json').status_code, 405)
        self.assertEqual(client.delete(f'{LOGS}{self.login.id}/').status_code, 405)


class AuditImmutabilityTests(TestCase):
    def setUp(self):
        self.entry = AuditLog.log(event_type=AuditEventType.AUTH_LOGOUT, description='x')

    def test_instance_cannot_be_updated_or_deleted(self):
        self.entry.description = 'rewritten'

        with self.assertRaises(PermissionError):
            self.entry.save()
        with self.assertRaises(PermissionError):
            self.entry.delete()

    def test_queryset_bulk_writes_are_blocked(self):
        # Regression: the guard lived on the Manager only, so
        # AuditLog.objects.filter(...).update()/.delete() still worked.
        with self.assertRaises(PermissionError):
            AuditLog.objects.filter(pk=self.entry.pk).update(description='rewritten')
        with self.assertRaises(PermissionError):
            AuditLog.objects.filter(pk=self.entry.pk).delete()
        with self.assertRaises(PermissionError):
            AuditLog.objects.all().delete()

        self.entry.refresh_from_db()
        self.assertEqual(self.entry.description, 'x')

    def test_identity_reveal_log_is_append_only_too(self):
        entry = IdentityRevealLog.objects.create(
            janmitra_user_id='u1', revealed_to_user_id='u2', revealed_to_role='L1',
            approved_by_user_id='u3', justification='j',
        )

        with self.assertRaises(PermissionError):
            IdentityRevealLog.objects.filter(pk=entry.pk).delete()
        with self.assertRaises(PermissionError):
            entry.save()


class AuditRecordingTests(TestCase):
    def test_device_fingerprint_is_stored_as_a_digest(self):
        # The fingerprint is the login credential for JanMitra users; the
        # audit table used to receive it verbatim from the request header.
        fingerprint = 'pixel-8-a1b2c3d4'
        request = RequestFactory().get('/api/v1/auth/me/', HTTP_X_DEVICE_FINGERPRINT=fingerprint)

        entry = AuditLog.log(event_type=AuditEventType.AUTH_LOGIN_SUCCESS, request=request)

        self.assertEqual(
            entry.device_fingerprint_hash, hashlib.sha256(fingerprint.encode()).hexdigest()
        )

    def test_janmitra_actor_is_pseudonymised(self):
        citizen = make_user(UserRole.JANMITRA, is_anonymous=True)

        entry = AuditLog.log(event_type=AuditEventType.REPORT_CREATED, actor=citizen)

        self.assertNotIn(citizen.identifier, entry.actor_identifier)
        self.assertTrue(entry.actor_identifier.startswith('JanMitra-'))

    def test_failed_login_is_audited_through_the_api(self):
        client_for().post(
            '/api/v1/auth/login/', {'identifier': 'ghost', 'password': 'x'}, format='json'
        )

        entry = AuditLog.objects.get(event_type=AuditEventType.AUTH_LOGIN_FAILED)
        self.assertFalse(entry.success)
        self.assertEqual(entry.request_path, '/api/v1/auth/login/')
