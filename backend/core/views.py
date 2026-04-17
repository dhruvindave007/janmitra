"""
Core views for JanMitra Backend.

Public endpoints that don't require authentication.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import AppVersionConfig


@api_view(['GET'])
@permission_classes([AllowAny])
def version_check(request):
    """
    Public endpoint for mobile app version checking.
    
    Returns the latest version info so the app can determine
    whether an update is available or required.
    
    No authentication needed — must work before login.
    Cache disabled — clients must always get fresh version data.
    """
    config = AppVersionConfig.get_active()
    
    if not config:
        data = {
            'latest_version': '1.0.0',
            'force_update': False,
            'apk_url': '',
            'release_notes': '',
        }
    else:
        data = {
            'latest_version': config.latest_version,
            'force_update': config.force_update,
            'apk_url': config.apk_url,
            'release_notes': config.release_notes,
        }
    
    response = Response(data)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response['Pragma'] = 'no-cache'
    return response
