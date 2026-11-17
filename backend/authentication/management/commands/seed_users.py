"""
Management command to seed demo users, one per role.

Usage:
    python manage.py seed_users                       # create if missing
    python manage.py seed_users --force               # reset passwords & roles
    python manage.py seed_users --password 'S3cret!'  # explicit password

Role hierarchy:
    L0  = Field Officer (station)      - works assigned cases
    L1  = PSO (station)                - assigns L0, manages station
    L2  = PI / Station Head (station)  - closes solved cases
    L3  = Regional authority           - handles escalated cases
    L4  = Zonal authority              - final escalation, no SLA
    JANMITRA = Citizen                 - submits incidents

Password selection, in order:
    1. --password
    2. the SEED_USER_PASSWORD environment variable
    3. DEV_DEFAULT_PASSWORD, only when DEBUG=True

With DEBUG=False and no explicit password the command refuses to run, so a
production deploy can never end up with well-known credentials on an L4
account.
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from authentication.models import User, UserRole, UserStatus

# Local development only. Never used when DEBUG is False.
DEV_DEFAULT_PASSWORD = 'Test@1234'

DEMO_USERS = [
    {'identifier': 'janmitra_user', 'role': UserRole.JANMITRA},
    {'identifier': 'l0_officer', 'role': UserRole.L0},
    {'identifier': 'l1_pso', 'role': UserRole.L1},
    {'identifier': 'l2_pi', 'role': UserRole.L2},
    {'identifier': 'l3_regional', 'role': UserRole.L3},
    {'identifier': 'l4_zonal', 'role': UserRole.L4},
]


class Command(BaseCommand):
    help = 'Seed demo/test users for all JanMitra roles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Reset passwords and roles even if users already exist',
        )
        parser.add_argument(
            '--password',
            help='Password for every seeded user (overrides SEED_USER_PASSWORD)',
        )

    def _resolve_password(self, options):
        password = options.get('password') or os.environ.get('SEED_USER_PASSWORD')
        if password:
            return password
        if settings.DEBUG:
            return DEV_DEFAULT_PASSWORD
        raise CommandError(
            'Refusing to seed users with the development default password while '
            'DEBUG=False. Pass --password or set SEED_USER_PASSWORD.'
        )

    def handle(self, *args, **options):
        force = options['force']
        password = self._resolve_password(options)
        created_count = 0
        updated_count = 0

        for user_data in DEMO_USERS:
            identifier = user_data['identifier']
            role = user_data['role']

            try:
                user = User.objects.get(identifier=identifier)
                if force:
                    user.set_password(password)
                    user.role = role
                    user.status = UserStatus.ACTIVE
                    user.is_active = True
                    user.save()
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(
                        f'  Updated: {identifier} (role={role})'
                    ))
                else:
                    self.stdout.write(self.style.NOTICE(
                        f'  Exists:  {identifier} (role={user.role}) — use --force to reset'
                    ))
            except User.DoesNotExist:
                user = User.objects.create_user(
                    identifier=identifier,
                    password=password,
                    role=role,
                )
                user.status = UserStatus.ACTIVE
                user.is_active = True
                user.save()
                created_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  Created: {identifier} (role={role})'
                ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done! Created: {created_count}, Updated: {updated_count}'
        ))
