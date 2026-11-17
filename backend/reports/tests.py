"""Tests for the incident -> case workflow: scoping, actions, media, SLA."""

from datetime import timedelta
from io import BytesIO, StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from PIL import Image

from authentication.models import UserRole
from core.testing import client_for, make_case, make_station, make_user
from reports.access import can_download_incident_media
from reports.models import (
    Case, CaseStatus, CaseStatusHistory, EscalationHistory, IncidentMedia,
)
from reports.services.escalation import EscalationService
from reports.tasks import escalate_sla_breaches

CASES = '/api/v1/incidents/cases/'
BROADCAST = '/api/v1/incidents/broadcast/'


def case_url(case, action=''):
    return f'{CASES}{case.id}/{action}'


def png_upload(name='evidence.png'):
    buffer = BytesIO()
    Image.new('RGB', (800, 600), (200, 30, 30)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


class WorkflowTestCase(TestCase):
    """Two stations, a full set of officers at the first one."""

    @classmethod
    def setUpTestData(cls):
        cls.alpha = make_station('Alpha')
        cls.beta = make_station('Beta')
        cls.l0 = make_user(UserRole.L0, station=cls.alpha)
        cls.l0_other = make_user(UserRole.L0, station=cls.alpha)
        cls.l1 = make_user(UserRole.L1, station=cls.alpha)
        cls.l2 = make_user(UserRole.L2, station=cls.alpha)
        cls.l3 = make_user(UserRole.L3, assigned_stations=[cls.alpha])
        cls.l4 = make_user(UserRole.L4)
        cls.l1_beta = make_user(UserRole.L1, station=cls.beta)
        cls.l2_beta = make_user(UserRole.L2, station=cls.beta)
        cls.citizen = make_user(UserRole.JANMITRA, station=cls.alpha)


class CaseVisibilityTests(WorkflowTestCase):
    def setUp(self):
        self.alpha_case = make_case(self.alpha)
        self.beta_case = make_case(self.beta)

    def ids(self, user, path=CASES):
        response = client_for(user).get(path)
        self.assertEqual(response.status_code, 200, response.data)
        return {row['id'] for row in response.data['results']}

    def test_station_officers_see_only_their_station(self):
        self.assertEqual(self.ids(self.l1), {str(self.alpha_case.id)})
        self.assertEqual(self.ids(self.l1_beta), {str(self.beta_case.id)})

    def test_l0_sees_only_assigned_cases(self):
        self.assertEqual(self.ids(self.l0), set())
        Case.objects.filter(pk=self.alpha_case.pk).update(assigned_officer=self.l0)
        self.assertEqual(self.ids(self.l0), {str(self.alpha_case.id)})

    def test_l3_sees_only_escalated_cases_from_assigned_stations(self):
        self.assertEqual(self.ids(self.l3), set())
        Case.objects.filter(pk__in=[self.alpha_case.pk, self.beta_case.pk]).update(
            current_level='L3'
        )
        self.assertEqual(self.ids(self.l3), {str(self.alpha_case.id)})

    def test_l4_sees_everything(self):
        self.assertEqual(
            self.ids(self.l4), {str(self.alpha_case.id), str(self.beta_case.id)}
        )

    def test_janmitra_sees_no_cases(self):
        self.assertEqual(self.ids(self.citizen), set())
        self.assertEqual(
            client_for(self.citizen).get(case_url(self.alpha_case)).status_code, 403
        )

    def test_detail_is_forbidden_across_stations(self):
        self.assertEqual(client_for(self.l1).get(case_url(self.alpha_case)).status_code, 200)
        self.assertEqual(
            client_for(self.l1_beta).get(case_url(self.alpha_case)).status_code, 403
        )

    def test_open_and_feed_follow_the_same_scope(self):
        # Regression: both endpoints compared the 'L1' string level against
        # legacy integer levels and returned nothing for every L0-L4 user.
        make_case(self.alpha, status=CaseStatus.CLOSED)

        open_ids = self.ids(self.l1, f'{CASES}open/')
        feed_ids = self.ids(self.l1, '/api/v1/incidents/feed/')

        self.assertEqual(open_ids, {str(self.alpha_case.id)})
        self.assertIn(str(self.alpha_case.id), feed_ids)
        self.assertNotIn(str(self.beta_case.id), feed_ids)
        self.assertEqual(len(feed_ids), 2)  # includes the closed alpha case

    def test_open_cases_are_ordered_most_urgent_first(self):
        urgent = make_case(self.alpha, sla_deadline=timezone.now() + timedelta(hours=1))

        response = client_for(self.l1).get(f'{CASES}open/')

        self.assertEqual(response.data['results'][0]['id'], str(urgent.id))


class CaseListPerformanceTests(WorkflowTestCase):
    def count_queries(self):
        client = client_for(self.l1)
        with self.assertNumQueries(self._expected):
            response = client.get(CASES)
        return response

    def test_query_count_does_not_grow_with_page_size(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        client = client_for(self.l1)
        make_case(self.alpha)
        with CaptureQueriesContext(connection) as one_row:
            client.get(CASES)

        for _ in range(9):
            make_case(self.alpha)
        with CaptureQueriesContext(connection) as ten_rows:
            response = client.get(CASES)

        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(len(ten_rows), len(one_row))

    def test_media_count_is_reported_per_case(self):
        case = make_case(self.alpha)
        IncidentMedia.objects.create(
            incident=case.incident, file=png_upload(), media_type='photo',
            original_filename='a.png', file_size=10, uploaded_by=self.citizen,
        )

        row = client_for(self.l1).get(CASES).data['results'][0]

        self.assertEqual(row['media_count'], 1)
        self.assertTrue(row['has_media'])

    def test_page_size_is_client_selectable_but_capped(self):
        for _ in range(3):
            make_case(self.alpha)
        client = client_for(self.l1)

        small = client.get(CASES, {'page_size': 2})
        huge = client.get(CASES, {'page_size': 100000})

        self.assertEqual(len(small.data['results']), 2)
        self.assertEqual(small.data['count'], 3)
        self.assertEqual(huge.status_code, 200)
        self.assertEqual(len(huge.data['results']), 3)


class CaseActionScopeTests(WorkflowTestCase):
    """Role alone is not enough: the case must be inside the caller's scope."""

    def setUp(self):
        self.case = make_case(self.alpha)

    def test_other_station_cannot_act_on_a_case(self):
        outsider = client_for(self.l1_beta)
        attempts = {
            'notes/': {'content': 'tampering'},
            'solve/': {'solution_notes': 'tampering'},
            'reject/': {'reason': 'tampering'},
            'forward/': {'reason': 'tampering'},
        }

        for action, payload in attempts.items():
            with self.subTest(action=action):
                response = outsider.post(case_url(self.case, action), payload, format='json')
                self.assertEqual(response.status_code, 403)

        self.case.refresh_from_db()
        self.assertEqual(self.case.status, CaseStatus.NEW)
        self.assertEqual(self.case.current_level, 'L1')
        self.assertEqual(self.case.notes.count(), 0)

    def test_other_station_l2_cannot_close_a_solved_case(self):
        Case.objects.filter(pk=self.case.pk).update(status=CaseStatus.SOLVED)

        response = client_for(self.l2_beta).post(case_url(self.case, 'close/'), {}, format='json')

        self.assertEqual(response.status_code, 403)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, CaseStatus.SOLVED)

    def test_unassigned_l0_cannot_solve(self):
        response = client_for(self.l0).post(case_url(self.case, 'solve/'), {}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_unknown_case_is_404(self):
        response = client_for(self.l1).post(
            f'{CASES}00000000-0000-4000-8000-000000000000/solve/', {}, format='json'
        )
        self.assertEqual(response.status_code, 404)

    def test_janmitra_cannot_act_on_cases(self):
        response = client_for(self.citizen).post(case_url(self.case, 'solve/'), {}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_assign_solve_close_happy_path(self):
        l1, l0, l2 = client_for(self.l1), client_for(self.l0), client_for(self.l2)

        assigned = l1.post(case_url(self.case, 'assign/'), {'officer_id': str(self.l0.id)}, format='json')
        noted = l0.post(case_url(self.case, 'notes/'), {'content': 'Visited the scene.'}, format='json')
        solved = l0.post(case_url(self.case, 'solve/'), {'solution_notes': 'Recovered.'}, format='json')
        early_close = l1.post(case_url(self.case, 'close/'), {}, format='json')
        closed = l2.post(case_url(self.case, 'close/'), {}, format='json')

        self.assertEqual(assigned.status_code, 200, assigned.data)
        self.assertEqual(noted.status_code, 201, noted.data)
        self.assertEqual(solved.status_code, 200, solved.data)
        self.assertEqual(early_close.status_code, 403)  # L1 cannot close
        self.assertEqual(closed.status_code, 200, closed.data)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, CaseStatus.CLOSED)
        self.assertEqual(self.case.solved_by, self.l0)
        self.assertEqual(self.case.closed_by, self.l2)

    def test_l1_cannot_assign_an_officer_from_another_station(self):
        foreign_l0 = make_user(UserRole.L0, station=self.beta)

        response = client_for(self.l1).post(
            case_url(self.case, 'assign/'), {'officer_id': str(foreign_l0.id)}, format='json'
        )

        self.assertEqual(response.status_code, 400)

    def test_reject_requires_a_reason(self):
        client = client_for(self.l1)

        self.assertEqual(client.post(case_url(self.case, 'reject/'), {}, format='json').status_code, 400)
        ok = client.post(case_url(self.case, 'reject/'), {'reason': 'Duplicate'}, format='json')
        self.assertEqual(ok.status_code, 200)


class ForwardCaseTests(WorkflowTestCase):
    def setUp(self):
        self.case = make_case(self.alpha)

    def test_forward_escalates_station_case_to_l3_then_l4(self):
        # Regression: this endpoint did integer arithmetic on the string
        # level column and failed with TypeError (HTTP 500) on every call.
        first = client_for(self.l1).post(
            case_url(self.case, 'forward/'), {'reason': 'Needs regional support'}, format='json'
        )
        self.case.refresh_from_db()

        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data['to_level'], 'L3')
        self.assertEqual(self.case.current_level, 'L3')
        self.assertEqual(self.case.status, CaseStatus.ESCALATED)
        self.assertEqual(self.case.escalation_count, 1)

        second = client_for(self.l3).post(case_url(self.case, 'forward/'), {}, format='json')
        self.case.refresh_from_db()
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(self.case.current_level, 'L4')

        final = client_for(self.l4).post(case_url(self.case, 'forward/'), {}, format='json')
        self.assertEqual(final.status_code, 400)

    def test_forward_records_history_and_is_not_an_sla_breach(self):
        client_for(self.l1).post(case_url(self.case, 'forward/'), {'reason': 'x'}, format='json')
        self.case.refresh_from_db()

        history = CaseStatusHistory.objects.filter(case=self.case, to_level='L3').get()
        self.assertEqual(history.changed_by, self.l1)
        self.assertFalse(history.is_auto_escalation)
        self.assertTrue(EscalationHistory.objects.filter(case=self.case, to_level='L3').exists())
        self.assertIsNone(self.case.sla_breached_at)

    def test_closed_case_cannot_be_forwarded(self):
        Case.objects.filter(pk=self.case.pk).update(status=CaseStatus.CLOSED)

        response = client_for(self.l1).post(case_url(self.case, 'forward/'), {}, format='json')

        self.assertEqual(response.status_code, 400)

    def test_escalated_level_never_decreases(self):
        EscalationService.escalate_case(self.case, escalated_by=self.l1)
        self.case.refresh_from_db()

        self.case.current_level = 'L1'
        self.case.save()
        self.case.refresh_from_db()

        self.assertEqual(self.case.current_level, 'L3')


class SlaEscalationTests(WorkflowTestCase):
    def setUp(self):
        past = timezone.now() - timedelta(hours=1)
        self.breached = make_case(self.alpha, sla_deadline=past)
        self.on_time = make_case(self.alpha)
        self.closed = make_case(self.alpha, sla_deadline=past, status=CaseStatus.CLOSED)

    def test_command_escalates_only_breached_active_cases(self):
        out = StringIO()

        call_command('auto_escalate_cases', stdout=out)

        self.breached.refresh_from_db()
        self.on_time.refresh_from_db()
        self.closed.refresh_from_db()
        self.assertEqual(self.breached.current_level, 'L3')
        self.assertEqual(self.breached.status, CaseStatus.ESCALATED)
        self.assertIsNotNone(self.breached.sla_breached_at)
        self.assertGreater(self.breached.sla_deadline, timezone.now())
        self.assertEqual(self.on_time.current_level, 'L1')
        self.assertEqual(self.closed.current_level, 'L1')
        self.assertIn('Escalated 1 case(s)', out.getvalue())

    def test_command_is_idempotent(self):
        call_command('auto_escalate_cases', stdout=StringIO())
        call_command('auto_escalate_cases', stdout=StringIO())

        self.breached.refresh_from_db()
        self.assertEqual(self.breached.current_level, 'L3')
        self.assertEqual(self.breached.escalation_count, 1)

    def test_dry_run_changes_nothing(self):
        out = StringIO()

        call_command('auto_escalate_cases', '--dry-run', stdout=out)

        self.breached.refresh_from_db()
        self.assertEqual(self.breached.current_level, 'L1')
        self.assertIn('1 case(s) would be escalated', out.getvalue())

    def test_periodic_task_escalates_and_notifies_once(self):
        from notifications.models import Notification

        escalated = escalate_sla_breaches.delay().get()

        self.assertEqual(escalated, 1)
        # One notification for the single L3 officer covering this station.
        self.assertEqual(Notification.objects.filter(recipient=self.l3).count(), 1)

    def test_l4_cases_have_no_sla(self):
        Case.objects.filter(pk=self.breached.pk).update(current_level='L4')

        self.assertEqual(escalate_sla_breaches.delay().get(), 0)


class BroadcastTests(WorkflowTestCase):
    def payload(self, **overrides):
        data = {
            'description': 'Two men snatched a gold chain and fled on a motorbike.',
            'incident_location': 'Opposite City Mall, Ring Road',
            'category': 'THEFT',
            'latitude': '23.0225',
            'longitude': '72.5714',
        }
        data.update(overrides)
        return data

    def test_citizen_report_creates_case_at_assigned_station(self):
        response = client_for(self.citizen).post(BROADCAST, self.payload(), format='json')

        self.assertEqual(response.status_code, 201, response.data)
        case = Case.objects.get(id=response.data['case_id'])
        self.assertEqual(case.police_station, self.alpha)
        self.assertEqual(case.current_level, 'L1')
        self.assertEqual(case.status, CaseStatus.NEW)
        self.assertAlmostEqual(
            (case.sla_deadline - timezone.now()).total_seconds(), 48 * 3600, delta=60
        )

    def test_station_officers_are_notified(self):
        from notifications.models import Notification

        client_for(self.citizen).post(BROADCAST, self.payload(), format='json')

        recipients = set(Notification.objects.values_list('recipient_id', flat=True))
        self.assertIn(self.l1.id, recipients)
        self.assertIn(self.l2.id, recipients)
        self.assertNotIn(self.l1_beta.id, recipients)

    def test_non_numeric_coordinates_are_a_validation_error(self):
        # Regression: Decimal('abc') raised InvalidOperation -> HTTP 500.
        response = client_for(self.citizen).post(
            BROADCAST, self.payload(latitude='abc'), format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Case.objects.exists())

    def test_out_of_range_coordinates_are_rejected(self):
        response = client_for(self.citizen).post(
            BROADCAST, self.payload(latitude='123.0'), format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_required_fields(self):
        client = client_for(self.citizen)
        for field in ('description', 'incident_location', 'category', 'latitude'):
            with self.subTest(field=field):
                payload = self.payload()
                payload.pop(field)
                self.assertEqual(client.post(BROADCAST, payload, format='json').status_code, 400)

    def test_vague_location_is_rejected(self):
        response = client_for(self.citizen).post(
            BROADCAST, self.payload(incident_location='nearby area'), format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_citizen_without_station_cannot_report(self):
        unassigned = make_user(UserRole.JANMITRA)

        response = client_for(unassigned).post(BROADCAST, self.payload(), format='json')

        self.assertEqual(response.status_code, 400)

    def test_media_is_attached_and_invalid_files_reported(self):
        payload = self.payload()
        payload['media_files'] = [
            png_upload(),
            SimpleUploadedFile('notes.exe', b'MZ', content_type='application/octet-stream'),
        ]

        response = client_for(self.citizen).post(BROADCAST, payload, format='multipart')

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['media_uploaded'], 1)
        self.assertEqual(len(response.data['media_errors']), 1)


class IncidentMediaAccessTests(WorkflowTestCase):
    def setUp(self):
        self.case = make_case(self.alpha, submitted_by=self.citizen, assigned_officer=self.l0)
        self.media = IncidentMedia.objects.create(
            incident=self.case.incident,
            file=png_upload(),
            media_type='photo',
            original_filename='scene "1".png',
            file_size=1234,
            content_type='image/png',
            uploaded_by=self.citizen,
        )
        base = '/api/v1/incidents/'
        self.list_url = f'{base}{self.case.incident_id}/media/list/'
        self.download_url = f'{base}media/{self.media.id}/download/'
        self.preview_url = f'{base}media/{self.media.id}/preview/'

    def test_download_role_policy(self):
        allowed = [UserRole.L1, UserRole.L2, UserRole.L3, UserRole.L4,
                   UserRole.LEVEL_0, UserRole.LEVEL_1, UserRole.LEVEL_2_CAPTAIN]
        denied = [UserRole.L0, UserRole.LEVEL_2, UserRole.JANMITRA, UserRole.LEVEL_3]

        for role in allowed:
            self.assertTrue(can_download_incident_media(make_user(role)), role)
        for role in denied:
            self.assertFalse(can_download_incident_media(make_user(role)), role)

    def test_station_supervisor_can_download(self):
        # Regression: only legacy role names were allowed, so no L0-L4 user
        # could ever download, while the list endpoint claimed they could.
        response = client_for(self.l1).get(self.download_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))

    def test_uploader_filename_cannot_break_out_of_the_header(self):
        response = client_for(self.l1).get(self.download_url)

        # The embedded quotes must be escaped, not terminate the filename.
        self.assertNotIn('filename="scene "1".png"', response['Content-Disposition'])
        b''.join(response.streaming_content)

    def test_assigned_field_officer_gets_preview_but_not_download(self):
        client = client_for(self.l0)

        download = client.get(self.download_url)
        preview = client.get(self.preview_url)

        self.assertEqual(download.status_code, 403)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview['Content-Type'], 'image/jpeg')
        thumbnail = Image.open(BytesIO(b''.join(preview.streaming_content)))
        self.assertLessEqual(max(thumbnail.size), 400)

    def test_other_station_cannot_list_download_or_preview(self):
        outsider = client_for(self.l1_beta)

        for url in (self.list_url, self.download_url, self.preview_url):
            with self.subTest(url=url):
                self.assertEqual(outsider.get(url).status_code, 403)

    def test_unassigned_field_officer_cannot_preview(self):
        self.assertEqual(client_for(self.l0_other).get(self.preview_url).status_code, 403)

    def test_citizen_cannot_read_media_back(self):
        client = client_for(self.citizen)

        self.assertEqual(client.get(self.download_url).status_code, 403)
        self.assertEqual(client.get(self.preview_url).status_code, 403)

    def test_list_and_detail_agree_with_the_download_endpoint(self):
        for user, expected in ((self.l1, True), (self.l0, False)):
            with self.subTest(role=user.role):
                listing = client_for(user).get(self.list_url).data
                detail = client_for(user).get(case_url(self.case)).data

                self.assertEqual(listing[0]['can_download'], expected)
                self.assertEqual(detail['can_download_media'], expected)
                self.assertEqual(detail['media_files'][0]['can_download'], expected)

    def test_raw_media_url_is_not_public(self):
        from rest_framework.test import APIClient

        response = APIClient().get(f'/media/{self.media.file.name}')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])


class InvestigationChatTests(WorkflowTestCase):
    def setUp(self):
        self.case = make_case(self.alpha, assigned_officer=self.l0)
        self.send_url = case_url(self.case, 'messages/send/')
        self.list_url = case_url(self.case, 'messages/')

    def test_station_officers_can_chat(self):
        sent = client_for(self.l0).post(self.send_url, {'text': 'On my way.'}, format='json')
        listing = client_for(self.l1).get(self.list_url)

        self.assertEqual(sent.status_code, 201, sent.data)
        self.assertEqual(listing.data['count'], 1)

    def test_outsiders_cannot_read_or_write(self):
        for user in (self.l1_beta, self.l0_other, self.l3, self.citizen):
            with self.subTest(role=user.role):
                client = client_for(user)
                self.assertEqual(client.get(self.list_url).status_code, 403)
                self.assertEqual(
                    client.post(self.send_url, {'text': 'hi'}, format='json').status_code, 403
                )

    def test_only_the_author_can_delete_a_message(self):
        message_id = client_for(self.l0).post(
            self.send_url, {'text': 'typo'}, format='json'
        ).data['message']['id']
        url = f'/api/v1/incidents/messages/{message_id}/delete/'

        self.assertEqual(client_for(self.l1).delete(url).status_code, 403)
        self.assertEqual(client_for(self.l0).delete(url).status_code, 200)
