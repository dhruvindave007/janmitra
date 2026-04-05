"""
Audit logging middleware for JanMitra Backend.

Provides:
- Request ID generation and propagation (X-Request-ID)
- Structured request/response logging with slow-request detection
- Admin IP restriction (blocks by default in production)
"""

import json
import logging
import time
import uuid

from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils import timezone

import sentry_sdk

audit_logger = logging.getLogger('janmitra.audit')
security_logger = logging.getLogger('janmitra.security')

# Threshold for slow request warnings (seconds)
SLOW_REQUEST_THRESHOLD = 1.0


class RequestIDMiddleware:
    """
    Generates a unique request ID for every request.
    
    - Attaches to request object as `request.request_id`
    - Adds X-Request-ID response header for client tracing
    - Respects incoming X-Request-ID from mobile client or load balancer
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
    Structured request/response logging.
    
    Captures: request_id, method, path, user_id, role, status_code,
    duration_ms, IP. Warns on slow requests (>1s).
    
    NEVER logs: request body, Authorization header, tokens, passwords.
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
        """Log structured request data as JSON. No sensitive data."""
        user_id = 'anonymous'
        user_role = 'none'
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = str(request.user.id)
            user_role = getattr(request.user, 'role', 'unknown')
        
        duration_ms = round(duration * 1000, 2)
        
        log_data = {
            'request_id': getattr(request, 'request_id', '-'),
            'timestamp': timezone.now().isoformat(),
            'method': request.method,
            'path': request.path,
            'user_id': user_id,
            'user_role': user_role,
            'status_code': response.status_code,
            'duration_ms': duration_ms,
            'ip_address': self._get_client_ip(request),
        }
        
        log_line = json.dumps(log_data, default=str)
        
        # Slow request detection
        if duration >= SLOW_REQUEST_THRESHOLD:
            audit_logger.warning(
                f"SLOW_REQUEST duration={duration_ms}ms {log_line}"
            )
            sentry_sdk.set_tag('slow_request', True)
        elif response.status_code >= 500:
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
    Restricts Django admin access by IP address.
    
    Behavior:
    - DEBUG=True  → admin unrestricted (development)
    - DEBUG=False → admin BLOCKED unless client IP is in ADMIN_ALLOWED_IPS
    
    Configure ADMIN_ALLOWED_IPS in .env as comma-separated IPs.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.path.startswith('/admin/'):
            # In production (DEBUG=False), block by default
            if not getattr(settings, 'DEBUG', False):
                allowed_ips = getattr(settings, 'ADMIN_ALLOWED_IPS', [])
                client_ip = self._get_client_ip(request)
                
                if not allowed_ips or client_ip not in allowed_ips:
                    security_logger.warning(
                        f"Admin access BLOCKED: ip={client_ip} path={request.path}"
                    )
                    sentry_sdk.capture_message(
                        f"Admin access blocked from {client_ip}",
                        level='warning',
                    )
                    return HttpResponseForbidden('Forbidden')
        
        return self.get_response(request)
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
