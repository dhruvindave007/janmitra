"""Tests for login, device binding, invite codes, sessions and seeding."""

import hashlib
import importlib
from io import StringIO
from unittest import mock

from django.apps import apps as django_apps
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import (
    DeviceSession, InviteCode, JanMitraProfile, User, UserRole,
)
from authentication.views import LoginThrottle
from core.testing import DEFAULT_PASSWORD, make_station, make_user

REGISTER = '/api/v1/auth/janmitra/register/'
JM_LOGIN = '/api/v1/auth/janmitra/login/'
LOGIN = '/api/v1/auth/login/'
REFRESH = '/api/v1/auth/token/refresh/'
LOGOUT = '/api/v1/auth/logout/'
ME = '/api/v1/auth/me/'


def sha256(value):
    return hashlib.sha256(value.encode()).hexdigest()


class JanMitraDeviceAuthTests(TestCase):
    """Invite-code registration followed by password-less device login."""

    def setUp(self):
        self.client = APIClient()
        self.issuer = make_user(UserRole.L1, station=make_station())
        self.invite = InviteCode.generate_code(issued_by=self.issuer)
        self.fingerprint = 'pixel-8-a1b2c3d4'

    def register(self, fingerprint=None, code=None):
        return self.client.post(REGISTER, {
            'invite_code': code or self.invite.code,
            'device_fingerprint': fingerprint or self.fingerprint,
        }, format='json')

    def test_registration_stores_only_the_fingerprint_digest(self):
        response = self.register()

        self.assertEqual(response.status_code, 201, response.data)
        profile = JanMitraProfile.objects.get()
        self.assertEqual(profile.device_fingerprint_hash, sha256(self.fingerprint))
        self.assertNotIn(self.fingerprint, profile.device_fingerprint_hash)

    def test_registered_device_can_log_in_again(self):
        # Regression: the raw fingerprint was stored at registration while
        # login searched by digest, so this always returned 400.
        self.register()

        response = self.client.post(
            JM_LOGIN, {'device_fingerprint': self.fingerprint}, format='json'
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('access', response.data)

    def test_fingerprint_longer_than_hash_column_is_accepted(self):
        long_fingerprint = 'f' * 200  # column is 64 chars; the digest always fits

        self.assertEqual(self.register(fingerprint=long_fingerprint).status_code, 201)
        response = self.client.post(
            JM_LOGIN, {'device_fingerprint': long_fingerprint}, format='json'
        )
        self.assertEqual(response.status_code, 200)

    def test_unknown_device_cannot_log_in(self):
        response = self.client.post(
            JM_LOGIN, {'device_fingerprint': 'never-registered'}, format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_single_use_invite_cannot_be_reused(self):
        self.assertEqual(self.register().status_code, 201)

        response = self.register(fingerprint='a-second-device')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(JanMitraProfile.objects.count(), 1)

    def test_same_device_cannot_register_twice(self):
        self.register()
        second_invite = InviteCode.generate_code(issued_by=self.issuer)

        response = self.register(code=second_invite.code)

        self.assertEqual(response.status_code, 400)

    def test_access_token_is_bound_to_the_registering_device(self):
        access = self.register().data['access']
        auth = {'HTTP_AUTHORIZATION': f'Bearer {access}'}

        ok = self.client.get(ME, HTTP_X_DEVICE_FINGERPRINT=self.fingerprint, **auth)
        missing = self.client.get(ME, **auth)
        other_device = self.client.get(ME, HTTP_X_DEVICE_FINGERPRINT='stolen-token', **auth)

        self.assertEqual(ok.status_code, 200)
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(other_device.status_code, 401)

    def test_login_after_revocation_and_reregistration_uses_the_live_account(self):
        # A device ends up with two profiles here; login must not crash with
        # MultipleObjectsReturned and must pick the active account.
        self.register()
        revoked = User.objects.get(role=UserRole.LEVEL_3)
        revoked.revoke_access(revoked_by=self.issuer, reason='test')

        second_invite = InviteCode.generate_code(issued_by=self.issuer)
        self.assertEqual(self.register(code=second_invite.code).status_code, 201)

        response = self.client.post(
            JM_LOGIN, {'device_fingerprint': self.fingerprint}, format='json'
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotEqual(response.data['user']['id'], str(revoked.id))

    def test_revoked_device_cannot_log_in(self):
        self.register()
        User.objects.get(role=UserRole.LEVEL_3).revoke_access(
            revoked_by=self.issuer, reason='test'
        )

        response = self.client.post(
            JM_LOGIN, {'device_fingerprint': self.fingerprint}, format='json'
        )

        self.assertEqual(response.status_code, 400)


class AuthorityAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.station = make_station()
        self.officer = make_user(UserRole.L1, station=self.station, identifier='pso_one')

    def login(self, password=DEFAULT_PASSWORD, **extra):
        return self.client.post(
            LOGIN, {'identifier': 'pso_one', 'password': password, **extra}, format='json'
        )

    def test_login_returns_tokens_and_role(self):
        response = self.login()

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['role'], UserRole.L1)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_wrong_password_is_rejected_and_counted(self):
        response = self.login(password='wrong')

        self.assertEqual(response.status_code, 400)
        self.officer.refresh_from_db()
        self.assertEqual(self.officer.failed_login_attempts, 1)

    def test_unknown_user_gets_the_same_error_as_wrong_password(self):
        unknown = self.client.post(
            LOGIN, {'identifier': 'nobody', 'password': 'x'}, format='json'
        )
        wrong = self.login(password='wrong')

        self.assertEqual(unknown.status_code, wrong.status_code)
        self.assertEqual(unknown.data, wrong.data)

    def test_refresh_rotates_and_blacklists_the_old_token(self):
        refresh = self.login().data['refresh']

        first = self.client.post(REFRESH, {'refresh': refresh}, format='json')
        replay = self.client.post(REFRESH, {'refresh': refresh}, format='json')

        self.assertEqual(first.status_code, 200)
        self.assertNotEqual(first.data['refresh'], refresh)
        self.assertEqual(replay.status_code, 401)

    def test_revoked_user_access_token_stops_working(self):
        access = self.login().data['access']
        admin = make_user(UserRole.L1, station=self.station)
        self.officer.revoke_access(revoked_by=admin, reason='left the force')

        response = self.client.get(ME, HTTP_AUTHORIZATION=f'Bearer {access}')

        self.assertEqual(response.status_code, 401)

    def test_logout_invalidates_refresh_token_and_session(self):
        tokens = self.login(device_fingerprint='desk-pc').data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.post(LOGOUT, {'refresh': tokens['refresh']}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(DeviceSession.objects.filter(is_active=True).exists())
        replay = self.client.post(REFRESH, {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(replay.status_code, 401)

    def test_cannot_log_out_someone_elses_refresh_token(self):
        victim_refresh = self.login().data['refresh']
        attacker = make_user(UserRole.L0, station=self.station, identifier='l0_attacker')
        attacker_tokens = self.client.post(
            LOGIN, {'identifier': 'l0_attacker', 'password': DEFAULT_PASSWORD}, format='json'
        ).data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {attacker_tokens['access']}")

        response = self.client.post(LOGOUT, {'refresh': victim_refresh}, format='json')

        self.assertEqual(response.status_code, 400)
        self.client.credentials()
        still_valid = self.client.post(REFRESH, {'refresh': victim_refresh}, format='json')
        self.assertEqual(still_valid.status_code, 200)

    def test_endpoints_require_authentication(self):
        self.assertEqual(self.client.get(ME).status_code, 401)
        self.assertEqual(self.client.get('/api/v1/incidents/cases/').status_code, 401)


class LoginThrottleTests(TestCase):
    """The 'login' rate was configured but never enforced."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        make_user(UserRole.L1, station=make_station(), identifier='pso_one')

    def test_repeated_login_attempts_are_rate_limited(self):
        client = APIClient()
        payload = {'identifier': 'pso_one', 'password': 'wrong'}

        with mock.patch.object(LoginThrottle, 'THROTTLE_RATES', {'login': '3/minute'}):
            statuses = [
                client.post(LOGIN, payload, format='json').status_code for _ in range(5)
            ]

        self.assertEqual(statuses, [400, 400, 400, 429, 429])

    def test_limit_also_covers_device_login_and_registration(self):
        client = APIClient()

        with mock.patch.object(LoginThrottle, 'THROTTLE_RATES', {'login': '1/minute'}):
            client.post(JM_LOGIN, {'device_fingerprint': 'x'}, format='json')
            second = client.post(JM_LOGIN, {'device_fingerprint': 'x'}, format='json')
            register = client.post(REGISTER, {}, format='json')

        self.assertEqual(second.status_code, 429)
        self.assertEqual(register.status_code, 429)


class InviteCodeTests(TestCase):
    def test_generate_code_sets_expiry(self):
        issuer = make_user(UserRole.L1, station=make_station())

        invite = InviteCode.generate_code(issued_by=issuer, expires_in_days=7)

        self.assertTrue(invite.is_valid)
        self.assertRegex(invite.code, r'^JM-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$')

    def test_janmitra_cannot_issue_invites(self):
        citizen = make_user(UserRole.JANMITRA)
        client = APIClient()
        client.force_authenticate(citizen)

        response = client.post('/api/v1/auth/invites/create/', {}, format='json')

        self.assertEqual(response.status_code, 403)


class FingerprintRepairMigrationTests(TestCase):
    def test_raw_values_are_hashed_and_digests_left_alone(self):
        issuer = make_user(UserRole.L1, station=make_station())
        raw_user = make_user(UserRole.JANMITRA)
        ok_user = make_user(UserRole.JANMITRA)
        raw = JanMitraProfile.objects.create(
            user=raw_user,
            device_fingerprint_hash='raw-device-id',
            invite_code=InviteCode.generate_code(issued_by=issuer),
        )
        already = JanMitraProfile.objects.create(
            user=ok_user,
            device_fingerprint_hash=sha256('other-device'),
            invite_code=InviteCode.generate_code(issued_by=issuer),
        )
        migration = importlib.import_module(
            'authentication.migrations.0008_hash_raw_device_fingerprints'
        )

        migration.hash_raw_fingerprints(django_apps, None)

        raw.refresh_from_db()
        already.refresh_from_db()
        self.assertEqual(raw.device_fingerprint_hash, sha256('raw-device-id'))
        self.assertEqual(already.device_fingerprint_hash, sha256('other-device'))


class SeedUsersCommandTests(TestCase):
    def test_refuses_default_password_outside_debug(self):
        with mock.patch.dict('os.environ', {}, clear=False) as env:
            env.pop('SEED_USER_PASSWORD', None)
            with self.assertRaises(CommandError):
                call_command('seed_users', stdout=StringIO())

        self.assertFalse(User.objects.exists())

    def test_explicit_password_creates_one_user_per_role(self):
        call_command('seed_users', password='Str0ng-Seed-Pass', stdout=StringIO())

        roles = set(User.objects.values_list('role', flat=True))
        self.assertEqual(
            roles,
            {UserRole.JANMITRA, UserRole.L0, UserRole.L1, UserRole.L2, UserRole.L3, UserRole.L4},
        )
        self.assertTrue(User.objects.get(identifier='l4_zonal').check_password('Str0ng-Seed-Pass'))

    @override_settings(DEBUG=True)
    def test_development_default_is_allowed_in_debug(self):
        with mock.patch.dict('os.environ', {}, clear=False) as env:
            env.pop('SEED_USER_PASSWORD', None)
            call_command('seed_users', stdout=StringIO())

        self.assertEqual(User.objects.count(), 6)
