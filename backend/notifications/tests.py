"""Tests for in-app notifications: ownership and read state."""

from django.test import TestCase

from authentication.models import UserRole
from core.testing import client_for, make_station, make_user
from notifications.models import Notification

BASE = '/api/v1/notifications/'


class NotificationApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        station = make_station()
        cls.owner = make_user(UserRole.L1, station=station)
        cls.other = make_user(UserRole.L2, station=station)
        cls.mine = Notification.objects.create(
            recipient=cls.owner, title='New case', message='A case was routed to you.'
        )
        cls.theirs = Notification.objects.create(
            recipient=cls.other, title='Case solved', message='Review and close.'
        )

    def test_list_contains_only_own_notifications(self):
        response = client_for(self.owner).get(BASE)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([n['id'] for n in response.data['results']], [str(self.mine.id)])

    def test_cannot_open_or_mark_someone_elses_notification(self):
        client = client_for(self.owner)

        self.assertEqual(client.get(f'{BASE}{self.theirs.id}/').status_code, 404)
        self.assertEqual(client.post(f'{BASE}{self.theirs.id}/read/').status_code, 404)
        self.theirs.refresh_from_db()
        self.assertFalse(self.theirs.is_read)

    def test_unread_count_and_mark_all_read(self):
        client = client_for(self.owner)

        self.assertEqual(client.get(f'{BASE}unread-count/').data['unread_count'], 1)
        self.assertEqual(client.post(f'{BASE}read-all/').data['count'], 1)
        self.assertEqual(client.get(f'{BASE}unread-count/').data['unread_count'], 0)
        self.theirs.refresh_from_db()
        self.assertFalse(self.theirs.is_read)

    def test_mark_single_read(self):
        response = client_for(self.owner).post(f'{BASE}{self.mine.id}/read/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_read'])

    def test_citizens_have_no_notification_inbox(self):
        citizen = make_user(UserRole.JANMITRA)

        self.assertEqual(client_for(citizen).get(BASE).status_code, 403)
