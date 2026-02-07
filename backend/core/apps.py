from django.apps import AppConfig
import logging
from django.conf import settings


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        logger = logging.getLogger(__name__)
        logger.info(f"ACCESS TOKEN LIFETIME: {settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']}")
