"""
Repair JanMitra profiles whose device fingerprint was stored unhashed.

Registration used to write the raw fingerprint into
``JanMitraProfile.device_fingerprint_hash`` while login looked the profile
up by its SHA-256 digest, so affected accounts could never log in again.
This rewrites every value that is not already a 64-character hex digest.
"""

import hashlib
import re

from django.db import migrations

_SHA256_HEX = re.compile(r'^[0-9a-f]{64}$')


def hash_raw_fingerprints(apps, schema_editor):
    JanMitraProfile = apps.get_model('authentication', 'JanMitraProfile')
    for profile in JanMitraProfile.objects.all().iterator():
        value = profile.device_fingerprint_hash or ''
        if value and not _SHA256_HEX.match(value):
            profile.device_fingerprint_hash = hashlib.sha256(value.encode()).hexdigest()
            profile.save(update_fields=['device_fingerprint_hash'])


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0007_add_assigned_stations_m2m'),
    ]

    operations = [
        # Hashing is one-way, so the reverse is intentionally a no-op.
        migrations.RunPython(hash_raw_fingerprints, migrations.RunPython.noop),
    ]
