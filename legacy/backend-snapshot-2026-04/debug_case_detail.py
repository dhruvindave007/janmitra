import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','janmitra_backend.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from reports.models import Case

case = Case.objects.first()
print('Using case id:', case.id if case else 'NO_CASE')
User = get_user_model()
from authentication.models import UserRole
# Select an authority user by role string
user = (
    User.objects.filter(role=UserRole.LEVEL_2).first()
    or User.objects.filter(role=UserRole.LEVEL_1).first()
    or User.objects.filter(is_superuser=True).first()
)
print('Using user:', getattr(user,'identifier', None))
client = APIClient()
if user:
    client.force_authenticate(user=user)

from reports.models import IncidentMedia

if not case:
    print('No case in DB to test')
else:
    url = f'/api/v1/incidents/cases/{case.id}/'
    print('GET', url)
    resp = client.get(url)
    print('STATUS', resp.status_code)
    print('DATA', resp.data)

# Find any incident with media
media_sample = IncidentMedia.objects.first()
if media_sample:
    print('\nFound media for incident:', media_sample.incident_id)
    # find case for that incident
    try:
        case_for_media = Case.objects.get(incident_id=media_sample.incident_id)
        print('Case id for media:', case_for_media.id)
        # Fetch list endpoint and check has_media
        list_resp = client.get('/api/v1/incidents/cases/?status=open')
        print('LIST STATUS', list_resp.status_code)
        for r in list_resp.data.get('results', []):
            if r.get('id') == str(case_for_media.id):
                print('Case in list has has_media:', r.get('has_media'), 'media_count:', r.get('media_count'))
    except Exception as e:
        print('Error fetching case for media:', e)
else:
    print('\nNo media rows exist in DB to test has_media flag')
