"""
Celery application for JanMitra.

Started by the ``celery`` service in docker-compose:

    celery -A janmitra_backend worker -B -l info

``-B`` embeds the beat scheduler so the periodic SLA escalation job
(``CELERY_BEAT_SCHEDULE`` in settings) runs without a separate container.
"""

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'janmitra_backend.settings')

app = Celery('janmitra_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
