"""
Shared request helpers.

Kept deliberately small: anything that needs to know *who* is calling
(client IP, device fingerprint) goes through here so the trust rules
live in exactly one place.
"""

import hashlib
import ipaddress

from django.conf import settings


def get_client_ip(request):
    """
    Return the client IP address for ``request``.

    ``X-Forwarded-For`` is attacker-controlled unless a trusted proxy
    rewrites it. A proxy *appends* the address it saw, so the only entries
    we can trust are the right-most ``TRUSTED_PROXY_COUNT`` ones. With one
    proxy (nginx) in front of the app the client address is therefore the
    last entry, never the first.

    When ``TRUSTED_PROXY_COUNT`` is 0 (the default, e.g. ``runserver``)
    the header is ignored entirely and ``REMOTE_ADDR`` is used.

    Returns ``None`` when no syntactically valid address is available, so
    the value is always safe to store in a ``GenericIPAddressField``.
    """
    if request is None:
        return None

    candidate = request.META.get('REMOTE_ADDR')
    trusted = getattr(settings, 'TRUSTED_PROXY_COUNT', 0)

    if trusted > 0:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        hops = [hop.strip() for hop in forwarded.split(',') if hop.strip()]
        if hops:
            # Clamp so a short header falls back to its left-most entry.
            candidate = hops[-min(trusted, len(hops))]

    try:
        return str(ipaddress.ip_address(candidate))
    except (TypeError, ValueError):
        return None


def hash_device_fingerprint(fingerprint):
    """SHA-256 hex digest of a device fingerprint ('' for empty input)."""
    if not fingerprint:
        return ''
    return hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()
