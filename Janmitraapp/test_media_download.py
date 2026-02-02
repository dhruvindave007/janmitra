import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','janmitra_backend.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from reports.models import IncidentMedia

media = IncidentMedia.objects.first()
print('media id', media.id)
User = get_user_model()
user = User.objects.filter(role='level_2').first() or User.objects.first()
client = APIClient(); client.force_authenticate(user=user)
url = f'/api/v1/incidents/media/{media.id}/download/'
print('GET', url)
resp = client.get(url)
print('status', resp.status_code)
if resp.status_code==200:
    # FileResponse streaming_content is an iterator of bytes
    data = b''.join(list(resp.streaming_content))
    print('content-length', len(data))
else:
    print('content-length', 'n/a')
