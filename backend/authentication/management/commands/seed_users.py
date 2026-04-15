"""
Management command to seed demo/test users for JanMitra.

Usage:
    python manage.py seed_users          # create if not exists
    python manage.py seed_users --force  # reset passwords & roles

Role hierarchy (correct canonical roles):
    L0  = Field Officer (station)      — works assigned cases
    L1  = PSO (station)                — assigns L0, manages station
    L2  = PI / Station Head (station)  — closes solved cases
    L3  = Regional authority           — handles escalated cases
    L4  = Zonal authority              — final escalation, no SLA
    JANMITRA = Citizen                 — submits incidents

All passwords: Test@1234
"""

from django.core.management.base import BaseCommand
from authentication.models import User, UserRole, UserStatus


DEMO_USERS = [
    {
        'identifier': 'janmitra_user',
        'password': 'Test@1234',
        'role': UserRole.JANMITRA,
    },
    {
        'identifier': 'l0_officer',
        'password': 'Test@1234',
        'role': UserRole.L0,
    },
    {
        'identifier': 'l1_pso',
        'password': 'Test@1234',
        'role': UserRole.L1,
    },
    {
        'identifier': 'l2_pi',
        'password': 'Test@1234',
        'role': UserRole.L2,
    },
    {
        'identifier': 'l3_regional',
        'password': 'Test@1234',
        'role': UserRole.L3,
    },
    {
        'identifier': 'l4_zonal',
        'password': 'Test@1234',
        'role': UserRole.L4,
    },
]


class Command(BaseCommand):
    help = 'Seed demo/test users for all JanMitra roles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Reset passwords and roles even if users already exist',
        )

    def handle(self, *args, **options):
        force = options['force']
        created_count = 0
        updated_count = 0

        for user_data in DEMO_USERS:
            identifier = user_data['identifier']
            password = user_data['password']
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
