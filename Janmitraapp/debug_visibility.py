import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','janmitra_backend.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from reports.models import visible_cases_for_user
from authentication.models import UserRole

User = get_user_model()
roles = [UserRole.LEVEL_2, UserRole.LEVEL_2_CAPTAIN, UserRole.LEVEL_1, UserRole.LEVEL_0]

for role in roles:
    user = User.objects.filter(role=role).first()
    print('\nROLE', role, 'user', getattr(user,'identifier', None))
    if not user:
        print('  no user for this role, skipping')
        continue
    qs = visible_cases_for_user(user)
    print('  visible cases count:', qs.count())
    if qs.count()==0:
        continue
    client = APIClient(); client.force_authenticate(user=user)
    for c in qs[:5]:
        url = f'/api/v1/incidents/cases/{c.id}/'
        resp = client.get(url)
        print('  case', c.id, '->', resp.status_code)
