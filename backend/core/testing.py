"""
Factories shared by the test suite.

Plain functions instead of a fixture library: the object graph is small
(station -> users -> incident -> case) and explicit construction keeps each
test readable.
"""

import itertools
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import User, UserRole, UserStatus
from core.models import PoliceStation
from reports.models import Case, CaseStatus, Incident, IncidentCategory

_seq = itertools.count(1)

DEFAULT_PASSWORD = 'correct-horse-battery-staple'


def make_station(name=None, **kwargs):
    n = next(_seq)
    defaults = {
        'name': name or f'Station {n}',
        'code': f'PS-{n:04d}',
        'latitude': Decimal('23.0225'),
        'longitude': Decimal('72.5714'),
        'city': 'Ahmedabad',
        'district': 'Ahmedabad',
        'state': 'Gujarat',
        'is_active': True,
    }
    defaults.update(kwargs)
    return PoliceStation.objects.create(**defaults)


def make_user(role, station=None, password=DEFAULT_PASSWORD, assigned_stations=(), **kwargs):
    n = next(_seq)
    user = User.objects.create_user(
        identifier=kwargs.pop('identifier', f'{role.lower()}_{n}'),
        password=password,
        role=role,
        status=UserStatus.ACTIVE,
        police_station=station,
        **kwargs,
    )
    if assigned_stations:
        user.assigned_stations.set(assigned_stations)
    return user


def make_case(station, submitted_by=None, level='L1', status=CaseStatus.NEW,
              assigned_officer=None, sla_deadline=None, **kwargs):
    submitted_by = submitted_by or make_user(UserRole.JANMITRA, station=station)
    incident = Incident.objects.create(
        submitted_by=submitted_by,
        text_content='Chain snatching reported near the bus stand.',
        incident_location='Bus stand, Station Road',
        category=IncidentCategory.THEFT,
        latitude=Decimal('23.0225'),
        longitude=Decimal('72.5714'),
    )
    return Case.objects.create(
        incident=incident,
        police_station=station,
        current_level=level,
        status=status,
        assigned_officer=assigned_officer,
        sla_deadline=sla_deadline or timezone.now() + timedelta(hours=48),
        **kwargs,
    )


def client_for(user=None):
    """APIClient authenticated as ``user`` (bypasses JWT; see auth tests for the real flow)."""
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client
