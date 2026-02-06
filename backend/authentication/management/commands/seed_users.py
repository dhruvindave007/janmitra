"""
Management command to seed demo/test users for JanMitra.

Usage:
    python manage.py seed_users

Creates users for all roles with known passwords for testing:
    - janmitra_demo / Demo@123 (Level-3 JanMitra)
    - level2@janmitra.gov.in / Level2@123 (Level-2 Field Officer)
    - captain@janmitra.gov.in / Captain@123 (Level-2 Captain)
    - level1@janmitra.gov.in / Level1@123 (Level-1 Senior Authority)
    - level0@janmitra.gov.in / Level0@123 (Level-0 Super Admin)
"""

from django.core.management.base import BaseCommand
from authentication.models import User, UserRole, UserStatus


DEMO_USERS = [
    {
        'identifier': 'janmitra_demo',
        'password': 'Demo@123',
        'role': UserRole.LEVEL_3,
        'full_name': 'JanMitra Demo User',
        'email': 'janmitra@demo.com',
    },
    {
        'identifier': 'level2@janmitra.gov.in',
        'password': 'Level2@123',
        'role': UserRole.LEVEL_2,
        'full_name': 'Level-2 Field Officer',
        'email': 'level2@janmitra.gov.in',
    },
    {
        'identifier': 'captain@janmitra.gov.in',
        'password': 'Captain@123',
        'role': UserRole.LEVEL_2_CAPTAIN,
        'full_name': 'Level-2 Captain',
        'email': 'captain@janmitra.gov.in',
    },
    {
        'identifier': 'level1@janmitra.gov.in',
        'password': 'Level1@123',
        'role': UserRole.LEVEL_1,
        'full_name': 'Level-1 Senior Authority',
        'email': 'level1@janmitra.gov.in',
    },
    {
        'identifier': 'level0@janmitra.gov.in',
        'password': 'Level0@123',
        'role': UserRole.LEVEL_0,
        'full_name': 'Level-0 Super Admin',
        'email': 'level0@janmitra.gov.in',
        'is_superuser': True,
        'is_staff': True,
    },
]


class Command(BaseCommand):
    help = 'Seed demo/test users for all JanMitra roles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Reset passwords even if users already exist',
        )

    def handle(self, *args, **options):
        force = options['force']
        created_count = 0
        updated_count = 0

        for user_data in DEMO_USERS:
            identifier = user_data.pop('identifier')
            password = user_data.pop('password')
            role = user_data.pop('role')
            is_superuser = user_data.pop('is_superuser', False)
            is_staff = user_data.pop('is_staff', False)
            # Remove fields that don't exist on User model
            user_data.pop('full_name', None)
            user_data.pop('email', None)

            try:
                user = User.objects.get(identifier=identifier)
                if force:
                    user.set_password(password)
                    user.role = role
                    user.status = UserStatus.ACTIVE
                    user.is_active = True
                    user.is_superuser = is_superuser
                    user.is_staff = is_staff
                    user.save()
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(
                        f'  Updated: {identifier} ({role})'
                    ))
                else:
                    self.stdout.write(self.style.NOTICE(
                        f'  Exists:  {identifier} ({user.role}) — use --force to reset'
                    ))
            except User.DoesNotExist:
                user = User.objects.create_user(
                    identifier=identifier,
                    password=password,
                    role=role,
                    **user_data,
                )
                user.status = UserStatus.ACTIVE
                user.is_active = True
                user.is_superuser = is_superuser
                user.is_staff = is_staff
                user.save()
                created_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  Created: {identifier} ({role})'
                ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done! Created: {created_count}, Updated: {updated_count}'
        ))
