"""
Management command to seed Ahmedabad police stations.

Seeds ~35 real Ahmedabad police stations with accurate GPS coordinates,
zone assignments, and jurisdiction area mappings.

Usage:
    python manage.py seed_ahmedabad_stations              # Create new only
    python manage.py seed_ahmedabad_stations --reset       # Deactivate old + create
    python manage.py seed_ahmedabad_stations --deactivate-test  # Deactivate test data
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import PoliceStation
from reports.services.ahmedabad_zones import AHMEDABAD_STATIONS

logger = logging.getLogger('janmitra.seed')


class Command(BaseCommand):
    help = 'Seed Ahmedabad police stations with real zone & area mappings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Deactivate all existing stations before seeding',
        )
        parser.add_argument(
            '--deactivate-test',
            action='store_true',
            help='Deactivate test/demo stations (non-Ahmedabad)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be done without making changes',
        )

    def handle(self, *args, **options):
        reset = options['reset']
        deactivate_test = options['deactivate_test']
        dry_run = options['dry_run']

        self.stdout.write(self.style.NOTICE(
            f"Seeding Ahmedabad police stations ({len(AHMEDABAD_STATIONS)} stations)..."
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be made\n"))

        with transaction.atomic():
            # Step 1: Deactivate old stations if requested
            if reset:
                count = PoliceStation.objects.filter(is_active=True).count()
                if not dry_run:
                    PoliceStation.objects.filter(is_active=True).update(is_active=False)
                self.stdout.write(self.style.WARNING(
                    f"  Deactivated {count} existing stations"
                ))

            if deactivate_test:
                test_qs = PoliceStation.objects.filter(is_active=True).exclude(
                    code__startswith='PS-GJ-AHM-'
                )
                count = test_qs.count()
                if not dry_run:
                    test_qs.update(is_active=False)
                self.stdout.write(self.style.WARNING(
                    f"  Deactivated {count} non-Ahmedabad stations"
                ))

            # Step 2: Create or update Ahmedabad stations
            created = 0
            updated = 0

            for data in AHMEDABAD_STATIONS:
                defaults = {
                    'name': data['name'],
                    'latitude': data['latitude'],
                    'longitude': data['longitude'],
                    'city': 'Ahmedabad',
                    'district': 'Ahmedabad',
                    'state': 'Gujarat',
                    'zone': data['zone'],
                    'jurisdiction_areas': ', '.join(data['areas']),
                    'address': data.get('address', ''),
                    'phone': data.get('phone', ''),
                    'is_active': True,
                }

                if dry_run:
                    exists = PoliceStation.objects.filter(code=data['code']).exists()
                    status = "UPDATE" if exists else "CREATE"
                    self.stdout.write(
                        f"  [{status}] {data['code']} — {data['name']} "
                        f"({data['zone']})"
                    )
                    if exists:
                        updated += 1
                    else:
                        created += 1
                else:
                    _, was_created = PoliceStation.objects.update_or_create(
                        code=data['code'],
                        defaults=defaults,
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

            # Summary
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                f"Done! Created: {created}, Updated: {updated}"
            ))

            # Print zone summary
            self.stdout.write(self.style.NOTICE("\nZone Summary:"))
            zones = {}
            for data in AHMEDABAD_STATIONS:
                zone = data['zone']
                zones.setdefault(zone, []).append(data['name'])

            for zone in sorted(zones.keys()):
                stations = zones[zone]
                self.stdout.write(
                    f"  {zone}: {len(stations)} stations"
                )
                for name in stations:
                    self.stdout.write(f"    • {name}")

            total_areas = sum(len(d['areas']) for d in AHMEDABAD_STATIONS)
            self.stdout.write(self.style.NOTICE(
                f"\nTotal: {len(AHMEDABAD_STATIONS)} stations, "
                f"{len(zones)} zones, {total_areas} mapped areas"
            ))
