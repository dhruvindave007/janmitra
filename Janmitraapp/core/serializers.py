"""
Serializers for the Core app.
"""
from rest_framework import serializers
from core.models import AppVersion


class AppVersionSerializer(serializers.ModelSerializer):
    """
    Serializer for app version information.
    
    Returns:
    - latest: The latest available version
    - minimum_supported: The minimum version that can still use the app
    - apk_url: Full URL to download the APK (None if no file attached)
    """
    
    apk_url = serializers.SerializerMethodField()
    
    class Meta:
        model = AppVersion
        fields = ['latest_version', 'minimum_supported_version', 'apk_url']
    
    def get_apk_url(self, obj):
        """
        Generate full URL to the APK file if one is attached.
        """
        if not obj.apk_file:
            return None
        
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.apk_file.url)
        
        # Fallback if no request context
        return f"/media/{obj.apk_file.name}"
