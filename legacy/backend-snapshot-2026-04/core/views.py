"""
Views for the Core app.

Handles system-level functionality like app version checking and updates.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from core.models import AppVersion
from core.serializers import AppVersionSerializer


class AppVersionView(APIView):
    """
    API endpoint for app version checking.
    
    GET /api/v1/app/version/
    
    Returns the latest available app version, minimum supported version,
    and the APK download URL. No authentication required.
    
    Response format:
    {
        "latest_version": "1.2.3",
        "minimum_supported_version": "1.0.0",
        "apk_url": "http://example.com/media/app_updates/janmitra-1.2.3.apk"
    }
    
    If no active version is configured, returns 404.
    """
    
    permission_classes = [AllowAny]  # Public endpoint for app updates
    
    def get(self, request):
        """
        Retrieve the currently active app version.
        """
        app_version = AppVersion.get_active_version()
        
        if not app_version:
            return Response(
                {'detail': 'No active app version configured'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AppVersionSerializer(app_version, context={'request': request})
        return Response(serializer.data)
