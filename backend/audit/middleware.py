"""
Audit logging middleware for JanMitra Backend.

Provides:
- Request ID generation and propagation (X-Request-ID)
- Structured request/response logging
- Admin IP restriction (production only)
"""

import json
import logging
import time
import uuid

from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils import timezone

audit_logger = logging.getLogger('janmitra.audit')
security_logger = logging.getLogger('janmitra.security')


class RequestIDMiddleware:
    """
    Generates a unique request ID for every request.
    
    - Attaches to request object as `request.request_id`
    - Adds X-Request-ID response header for client tracing
    - Respects incoming X-Request-ID from load balancer/proxy
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        request_id = request.META.get('HTTP_X_REQUEST_ID', str(uuid.uuid4()))
        request.request_id = request_id
        
        response = self.get_response(request)
        response['X-Request-ID'] = request_id
        return response


class AuditLoggingMiddleware:
    """
    Middleware to log all API requests for audit purposes.
    
    Captures:
    - Request ID (from RequestIDMiddleware)
    - Request method and path
    - User information (ID + role)
    - Response status code
    - Request duration in milliseconds
    - Client IP address
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        duration = time.time() - start_time
        
        if not self._should_skip(request.path):
            self._log_request(request, response, duration)
        
        return response
    
    def _should_skip(self, path):
        """Skip logging for static/health/media paths."""
        skip_prefixes = [
            '/static/',
            '/media/',
            '/health/',
            '/favicon.ico',
        ]
        return any(path.startswith(prefix) for prefix in skip_prefixes)
    
    def _log_request(self, request, response, duration):
        """Log structured request data as JSON."""
        user_id = 'anonymous'
        user_role = 'none'
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = str(request.user.id)
            user_role = getattr(request.user, 'role', 'unknown')
        
        log_data = {
            'request_id': getattr(request, 'request_id', '-'),
            'timestamp': timezone.now().isoformat(),
            'method': request.method,
            'path': request.path,
            'user_id': user_id,
            'user_role': user_role,
            'status_code': response.status_code,
            'duration_ms': round(duration * 1000, 2),
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
        }
        
        log_line = json.dumps(log_data, default=str)
        
        if response.status_code >= 500:
            audit_logger.error(log_line)
        elif response.status_code >= 400:
            audit_logger.warning(log_line)
        else:
            audit_logger.info(log_line)
    
    def _get_client_ip(self, request):
        """Extract client IP, respecting proxy headers."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class AdminIPRestrictionMiddleware:
    """
    Restricts Django admin access to allowed IP addresses in production.
    
    Configure via settings.ADMIN_ALLOWED_IPS (list of IPs).
    If not set or empty, admin is unrestricted (dev mode).
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.path.startswith('/admin/'):
            allowed_ips = getattr(settings, 'ADMIN_ALLOWED_IPS', [])
            if allowed_ips:
                client_ip = self._get_client_ip(request)
                if client_ip not in allowed_ips:
                    security_logger.warning(
                        f"Admin access denied: ip={client_ip} path={request.path}"
                    )
                    return HttpResponseForbidden('Forbidden')
        
        return self.get_response(request)
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
