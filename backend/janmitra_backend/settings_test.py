"""
Settings for the automated test suite.

    python manage.py test --settings=janmitra_backend.settings_test

Runs with DEBUG=False so tests exercise the production code paths, against
an in-memory SQLite database, with no dependency on Postgres, Redis or a
.env file.
"""

import os
import tempfile

# Must be set before the base settings module reads its environment.
os.environ.setdefault('SECRET_KEY', 'test-only-secret-key-not-used-anywhere-else')
os.environ['DEBUG'] = 'False'
os.environ['ALLOWED_HOSTS'] = 'testserver'
os.environ['DATABASE_ENGINE'] = 'django.db.backends.sqlite3'
os.environ['SECURE_SSL_REDIRECT'] = 'False'
os.environ['SENTRY_DSN'] = ''
os.environ['CACHE_URL'] = ''
os.environ['TRUSTED_PROXY_COUNT'] = '0'
os.environ['ADMIN_ALLOWED_IPS'] = ''

from .settings import *  # noqa: E402,F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Fast, deliberately weak hashing: tests create many users.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Uploaded files go to a throwaway directory, never the real media root.
MEDIA_ROOT = tempfile.mkdtemp(prefix='janmitra-test-media-')

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Run Celery tasks inline; no broker needed.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Rate limits are tested explicitly (authentication.tests); everywhere else
# they would only make unrelated tests order-dependent.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100000/minute',
        'user': '100000/minute',
        'login': '100000/minute',
    },
}

# Keep test output readable and do not write log files.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'root': {'handlers': ['null']},
}
