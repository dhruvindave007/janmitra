"""
URL configuration for JanMitra Backend.

API Structure:
- /api/v1/auth/     - Authentication endpoints
- /api/v1/reports/  - Report management
- /api/v1/media/    - Media management
- /api/v1/escalation/ - Escalation workflows
- /api/v1/audit/    - Audit logs (Level 1 only)
- /api/v1/app/      - App configuration & updates
- /admin/           - Django admin (restricted)
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static


def health_check(request):
    """Health check endpoint for load balancers."""
    return JsonResponse({
        'status': 'healthy',
        'service': 'janmitra-backend'
    })


def api_root(request):
    """API root endpoint with version info."""
    return JsonResponse({
        'name': 'JanMitra API',
        'version': 'v1',
        'endpoints': {
            'auth': '/api/v1/auth/',
            'reports': '/api/v1/reports/',
            'media': '/api/v1/media/',
            'escalation': '/api/v1/escalation/',
            'audit': '/api/v1/audit/',
            'app': '/api/v1/app/',
        }
    })


urlpatterns = [
    # Health check (public) - accessible at /health/ and /api/health/
    path('health/', health_check, name='health-check'),
    path('api/health/', health_check, name='api-health-check'),
    
    # API root
    path('api/v1/', api_root, name='api-root'),
    path('api/', api_root, name='api-root-short'),
    
    # Authentication endpoints
    path('api/v1/auth/', include('authentication.urls', namespace='auth')),
    
    # Report endpoints
    path('api/v1/reports/', include('reports.urls', namespace='reports')),
    
    # Incident endpoints (Case Lifecycle)
    path('api/v1/incidents/', include('reports.incident_urls', namespace='incidents')),
    
    # Media endpoints
    path('api/v1/media/', include('media_storage.urls', namespace='media')),
    
    # Escalation endpoints
    path('api/v1/escalation/', include('escalation.urls', namespace='escalation')),
    
    # Audit endpoints
    path('api/v1/audit/', include('audit.urls', namespace='audit')),
    
    # Notification endpoints
    path('api/v1/notifications/', include('notifications.urls', namespace='notifications')),
    
    # App configuration & update endpoints (version, APK download)
    path('api/v1/app/', include('core.urls', namespace='app')),
    
    # Django admin (restricted access)
    path('admin/', admin.site.urls),
]

# Serve media files during development (DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
