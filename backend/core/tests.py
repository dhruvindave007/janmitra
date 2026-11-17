"""Tests for cross-cutting pieces: client IP trust, settings, admin gate, health."""

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from authentication.models import UserRole
from core.models import AppVersionConfig
from core.testing import make_user
from core.utils import get_client_ip, hash_device_fingerprint


class ClientIpTests(SimpleTestCase):
    def request(self, remote='10.0.0.5', forwarded=None):
        extra = {'REMOTE_ADDR': remote}
        if forwarded is not None:
            extra['HTTP_X_FORWARDED_FOR'] = forwarded
        return RequestFactory().get('/', **extra)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_forwarded_header_is_ignored_without_a_trusted_proxy(self):
        request = self.request(remote='198.51.100.7', forwarded='203.0.113.9')

        self.assertEqual(get_client_ip(request), '198.51.100.7')

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_client_is_the_entry_appended_by_the_trusted_proxy(self):
        # The client sent "X-Forwarded-For: 203.0.113.9" itself; nginx then
        # appended the address it actually saw. Only the latter is real.
        request = self.request(forwarded='203.0.113.9, 198.51.100.7')

        self.assertEqual(get_client_ip(request), '198.51.100.7')

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_two_proxies(self):
        request = self.request(forwarded='203.0.113.9, 198.51.100.7, 10.0.0.2')

        self.assertEqual(get_client_ip(request), '198.51.100.7')

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_falls_back_to_remote_addr_when_header_is_missing(self):
        self.assertEqual(get_client_ip(self.request(remote='198.51.100.7')), '198.51.100.7')

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_garbage_is_never_returned(self):
        self.assertIsNone(get_client_ip(self.request(forwarded='<script>')))
        self.assertIsNone(get_client_ip(None))

    def test_fingerprint_hash(self):
        self.assertEqual(hash_device_fingerprint(''), '')
        self.assertEqual(len(hash_device_fingerprint('device')), 64)


class SettingsTests(SimpleTestCase):
    def test_allowed_hosts_is_never_a_wildcard(self):
        self.assertNotIn('*', settings.ALLOWED_HOSTS)
        self.assertIn('localhost', settings.ALLOWED_HOSTS)

    def test_unknown_host_is_rejected(self):
        response = self.client.get('/health/', HTTP_HOST='evil.example.com')

        self.assertEqual(response.status_code, 400)

    def test_upload_spool_threshold_is_not_the_old_500mb(self):
        self.assertLessEqual(settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 10 * 1024 * 1024)

    def test_cors_does_not_allow_credentials_by_default(self):
        self.assertFalse(settings.CORS_ALLOW_CREDENTIALS)

    def test_sla_job_is_scheduled(self):
        schedule = settings.CELERY_BEAT_SCHEDULE['escalate-sla-breaches']

        self.assertEqual(schedule['task'], 'reports.tasks.escalate_sla_breaches')


class AdminIpRestrictionTests(TestCase):
    """With DEBUG=False the admin is closed unless the client IP is listed."""

    def test_blocked_by_default(self):
        self.assertEqual(self.client.get('/admin/login/').status_code, 403)

    @override_settings(ADMIN_ALLOWED_IPS=['203.0.113.9'], TRUSTED_PROXY_COUNT=1)
    def test_allow_list_cannot_be_satisfied_by_a_spoofed_header(self):
        # Regression: the left-most X-Forwarded-For entry was trusted, so any
        # client could claim an allow-listed address.
        spoofed = self.client.get(
            '/admin/login/', HTTP_X_FORWARDED_FOR='203.0.113.9, 198.51.100.7'
        )
        genuine = self.client.get('/admin/login/', HTTP_X_FORWARDED_FOR='203.0.113.9')

        self.assertEqual(spoofed.status_code, 403)
        self.assertEqual(genuine.status_code, 200)

    @override_settings(ADMIN_ALLOWED_IPS=['127.0.0.1'])
    def test_direct_connection_from_allowed_address(self):
        self.assertEqual(self.client.get('/admin/login/').status_code, 200)


class ProtectedMediaTests(TestCase):
    def test_anonymous_request_is_sent_to_login(self):
        response = self.client.get('/media/incidents/anything.jpg')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_api_user_without_staff_flag_is_refused(self):
        officer = make_user(UserRole.L1)
        self.client.force_login(officer)

        response = self.client.get('/media/incidents/anything.jpg')

        self.assertEqual(response.status_code, 302)

    def test_staff_gets_404_for_missing_file_not_a_redirect(self):
        staff = make_user(UserRole.L4, is_staff=True)
        self.client.force_login(staff)

        response = self.client.get('/media/incidents/does-not-exist.jpg')

        self.assertEqual(response.status_code, 404)

    def test_path_traversal_is_rejected(self):
        staff = make_user(UserRole.L4, is_staff=True)
        self.client.force_login(staff)

        response = self.client.get('/media/../janmitra_backend/settings.py')

        self.assertIn(response.status_code, (400, 404))


class PublicEndpointTests(TestCase):
    def test_health(self):
        for path in ('/health/', '/api/health/'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'healthy')

    def test_version_check_defaults(self):
        response = self.client.get('/api/v1/app/version-check/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['latest_version'], '1.0.0')
        self.assertIn('no-store', response['Cache-Control'])

    def test_version_check_uses_active_config(self):
        AppVersionConfig.objects.create(
            latest_version='2.3.0', force_update=True,
            apk_url='https://example.com/app.apk', is_active=True,
        )

        data = self.client.get('/api/v1/app/version-check/').json()

        self.assertEqual(data['latest_version'], '2.3.0')
        self.assertTrue(data['force_update'])

    def test_error_responses_use_the_common_envelope(self):
        response = self.client.get('/api/v1/auth/me/')

        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertFalse(body['success'])
        self.assertEqual(body['error']['code'], 'UNAUTHORIZED')
        self.assertIn('request_id', body['error'])
        self.assertEqual(response['X-Request-ID'], body['error']['request_id'])
