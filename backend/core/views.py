"""
Core views for JanMitra Backend.

Public app endpoints plus the staff-only media file view.
"""

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.views.static import serve
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import AppVersionConfig


@staff_member_required
def protected_media(request, path):
    """
    Serve a file from MEDIA_ROOT to logged-in staff only.

    Incident photos, videos and chat attachments are evidence. They used to
    be reachable by anyone who knew or guessed the URL, because nginx
    aliased /media/ straight onto the upload directory (and Django did the
    same under DEBUG). Every request now passes through this view, which
    requires an authenticated staff session; nginx proxies /media/ here
    instead of reading the directory itself.
    """
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


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
