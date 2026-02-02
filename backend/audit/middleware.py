"""
Audit logging middleware for JanMitra Backend.

Automatically logs all API requests for security monitoring.
"""

import logging
import time
from django.utils import timezone

audit_logger = logging.getLogger('janmitra.audit')


class AuditLoggingMiddleware:
    """
    Middleware to log all API requests for audit purposes.
    
    Captures:
    - Request method and path
    - User information
    - Response status code
    - Request duration
    - Client IP address
    
    Note: This provides request-level logging. Action-level logging
    is done in views using the AuditLog.log() method.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Start timing
        start_time = time.time()
        
        # Get response
        response = self.get_response(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log the request (skip static files and health checks)
        if not self._should_skip(request.path):
            self._log_request(request, response, duration)
        
        return response
    
    def _should_skip(self, path):
        """Determine if this request should be skipped for logging."""
        skip_prefixes = [
            '/static/',
            '/media/',
            '/health/',
            '/favicon.ico',
        ]
        return any(path.startswith(prefix) for prefix in skip_prefixes)
    
    def _log_request(self, request, response, duration):
        """Log the request details."""
        user_id = 'anonymous'
        user_role = 'none'
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = str(request.user.id)
            user_role = request.user.role
        
        ip_address = self._get_client_ip(request)
        
        log_data = {
            'timestamp': timezone.now().isoformat(),
            'method': request.method,
            'path': request.path,
            'user_id': user_id,
            'user_role': user_role,
            'status_code': response.status_code,
            'duration_ms': round(duration * 1000, 2),
            'ip_address': ip_address,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
        }
        
        # Log at appropriate level based on status code
        if response.status_code >= 500:
            audit_logger.error(f"API Request: {log_data}")
        elif response.status_code >= 400:
            audit_logger.warning(f"API Request: {log_data}")
        else:
            audit_logger.info(f"API Request: {log_data}")
    
    def _get_client_ip(self, request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
