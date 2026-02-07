from django.apps import AppConfig
import logging
from django.conf import settings


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        """Log important runtime configuration on startup."""
        logger = logging.getLogger(__name__)
        access_lifetime = settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME')
        logger.info(f"ACCESS TOKEN LIFETIME: {access_lifetime}")

