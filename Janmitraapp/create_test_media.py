import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','janmitra_backend.settings')
import django
django.setup()
from django.core.files.base import ContentFile
from reports.models import IncidentMedia, Incident
from authentication.models import User

# find an incident
incident = Incident.objects.first()
if not incident:
    print('No incident found')
    exit(1)

u = User.objects.filter(is_superuser=True).first() or User.objects.first()

# Create a tiny 1x1 PNG
png_bytes = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\x9cc``\x00\x00\x00\x02\x00\x01\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82'
)

media = IncidentMedia(
    incident=incident,
    uploaded_by=u,
    media_type='photo',
)
media.file.save('test_thumbnail.png', ContentFile(png_bytes))
media.file_size = len(png_bytes)
media.content_type = 'image/png'
media.save()

print('Created media id:', media.id, 'for incident', incident.id)
