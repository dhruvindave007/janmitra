"""
Custom exception handling for JanMitra Backend.

Provides consistent error response format and security-aware error handling.
Never exposes sensitive information in error responses.
"""

import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

# Security logger for tracking suspicious activities
security_logger = logging.getLogger('janmitra.security')


def custom_exception_handler(exc, context):
    """
    Custom exception handler that:
    1. Provides consistent error response format
    2. Logs security-relevant exceptions
    3. Sanitizes error messages to prevent information leakage
    
    Response format:
    {
        "success": false,
        "error": {
            "code": "ERROR_CODE",
            "message": "User-friendly message",
            "details": {} (optional, only in debug mode)
        }
    }
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Get request info for logging
        request = context.get('request')
        view = context.get('view')
        
        # Prepare custom response
        custom_response = {
            'success': False,
            'error': {
                'code': _get_error_code(response.status_code),
                'message': _get_safe_message(exc, response.status_code),
            }
        }
        
        # Log security-relevant exceptions
        if response.status_code in [401, 403, 429]:
            _log_security_event(exc, request, view, response.status_code)
        
        response.data = custom_response
    
    return response


def _get_error_code(status_code):
    """Map HTTP status codes to error codes."""
    error_codes = {
        400: 'BAD_REQUEST',
        401: 'UNAUTHORIZED',
        403: 'FORBIDDEN',
        404: 'NOT_FOUND',
        405: 'METHOD_NOT_ALLOWED',
        409: 'CONFLICT',
        422: 'VALIDATION_ERROR',
        429: 'RATE_LIMIT_EXCEEDED',
        500: 'INTERNAL_ERROR',
        502: 'BAD_GATEWAY',
        503: 'SERVICE_UNAVAILABLE',
    }
    return error_codes.get(status_code, 'UNKNOWN_ERROR')


def _get_safe_message(exc, status_code):
    """
    Get a safe, user-friendly error message.
    Never expose internal details or stack traces.
    """
    safe_messages = {
        400: 'Invalid request. Please check your input.',
        401: 'Authentication required.',
        403: 'You do not have permission to perform this action.',
        404: 'The requested resource was not found.',
        405: 'This method is not allowed.',
        409: 'Request conflicts with current state.',
        422: 'Unable to process the request.',
        429: 'Too many requests. Please try again later.',
        500: 'An internal error occurred. Please try again later.',
        502: 'Service temporarily unavailable.',
        503: 'Service temporarily unavailable.',
    }
    
    # For validation errors (400), we can be more specific
    if status_code == 400 and hasattr(exc, 'detail'):
        if isinstance(exc.detail, dict):
            # Return first validation error
            for field, errors in exc.detail.items():
                if isinstance(errors, list) and errors:
                    return f"Validation error: {field} - {errors[0]}"
        elif isinstance(exc.detail, str):
            return exc.detail
    
    return safe_messages.get(status_code, 'An error occurred.')


def _log_security_event(exc, request, view, status_code):
    """Log security-relevant events for monitoring and alerting."""
    user_info = 'anonymous'
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        user_info = str(request.user.id)
    
    ip_address = _get_client_ip(request) if request else 'unknown'
    view_name = view.__class__.__name__ if view else 'unknown'
    
    security_logger.warning(
        f"Security event: status={status_code}, "
        f"user={user_info}, ip={ip_address}, "
        f"view={view_name}, exception={exc.__class__.__name__}"
    )


def _get_client_ip(request):
    """
    Extract client IP address from request.
    Handles proxy headers (X-Forwarded-For).
    """
    if not request:
        return 'unknown'
    
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the first IP in the chain (original client)
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    
    return ip


class JanMitraAPIException(Exception):
    """Base exception class for JanMitra-specific errors."""
    
    default_code = 'ERROR'
    default_message = 'An error occurred.'
    default_status_code = status.HTTP_400_BAD_REQUEST
    
    def __init__(self, message=None, code=None, status_code=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.status_code = status_code or self.default_status_code
        super().__init__(self.message)


class DeviceBindingError(JanMitraAPIException):
    """Raised when device binding validation fails."""
    default_code = 'DEVICE_BINDING_ERROR'
    default_message = 'Device verification failed.'
    default_status_code = status.HTTP_401_UNAUTHORIZED


class EncryptionError(JanMitraAPIException):
    """Raised when encryption/decryption operations fail."""
    default_code = 'ENCRYPTION_ERROR'
    default_message = 'Security operation failed.'
    default_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class RevocationError(JanMitraAPIException):
    """Raised when user access has been revoked."""
    default_code = 'ACCESS_REVOKED'
    default_message = 'Your access has been revoked.'
    default_status_code = status.HTTP_403_FORBIDDEN


class IdentityProtectionError(JanMitraAPIException):
    """Raised when attempting unauthorized identity access."""
    default_code = 'IDENTITY_PROTECTED'
    default_message = 'Identity information is protected.'
    default_status_code = status.HTTP_403_FORBIDDEN
