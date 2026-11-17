"""
Audit views: read-only access to the audit trail.

All audit logs are append-only and immutable.
Only Level 1 authorities have access to audit logs.
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.backends import DeviceBoundJWTAuthentication
from authentication.permissions import IsLevel1

from .models import AuditLog, IdentityRevealLog
from .serializers import AuditLogSerializer, IdentityRevealLogSerializer


class AuditLogFilter(filters.FilterSet):
    """
    Filters for the audit log listing.

    Query parameters: event_type, severity, success, actor_id, target_type,
    target_id, ip_address, timestamp_after, timestamp_before.
    """

    event_type = filters.CharFilter(field_name='event_type', lookup_expr='iexact')
    severity = filters.CharFilter(field_name='severity', lookup_expr='iexact')
    target_type = filters.CharFilter(field_name='target_type', lookup_expr='iexact')
    timestamp_after = filters.IsoDateTimeFilter(field_name='timestamp', lookup_expr='gte')
    timestamp_before = filters.IsoDateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = AuditLog
        fields = ['actor_id', 'target_id', 'ip_address', 'success']


class AuditLogListView(generics.ListAPIView):
    """
    List audit logs, newest first (paginated).

    GET /api/v1/audit/logs/
    """

    authentication_classes = [DeviceBoundJWTAuthentication]
    permission_classes = [IsLevel1]
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilter
    ordering_fields = ['timestamp', 'severity', 'event_type']
    ordering = ['-timestamp']
    queryset = AuditLog.objects.all()


class AuditLogDetailView(generics.RetrieveAPIView):
    """
    Retrieve one audit log entry.

    GET /api/v1/audit/logs/{id}/
    """

    authentication_classes = [DeviceBoundJWTAuthentication]
    permission_classes = [IsLevel1]
    serializer_class = AuditLogSerializer
    lookup_field = 'id'
    queryset = AuditLog.objects.all()


class IdentityRevealLogListView(generics.ListAPIView):
    """
    List identity reveal logs, newest first (paginated).

    GET /api/v1/audit/identity-reveals/
    """

    authentication_classes = [DeviceBoundJWTAuthentication]
    permission_classes = [IsLevel1]
    serializer_class = IdentityRevealLogSerializer
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']
    queryset = IdentityRevealLog.objects.all()


class IdentityRevealLogDetailView(generics.RetrieveAPIView):
    """
    Retrieve one identity reveal log entry.

    GET /api/v1/audit/identity-reveals/{id}/
    """

    authentication_classes = [DeviceBoundJWTAuthentication]
    permission_classes = [IsLevel1]
    serializer_class = IdentityRevealLogSerializer
    lookup_field = 'id'
    queryset = IdentityRevealLog.objects.all()


class AuditLogStatsView(APIView):
    """
    Aggregate audit statistics.

    GET /api/v1/audit/logs/stats/
    """

    authentication_classes = [DeviceBoundJWTAuthentication]
    permission_classes = [IsLevel1]

    def get(self, request):
        now = timezone.now()

        # One pass over the table instead of a COUNT query per window.
        totals = AuditLog.objects.aggregate(
            total=Count('id'),
            last_24_hours=Count('id', filter=Q(timestamp__gte=now - timedelta(hours=24))),
            last_7_days=Count('id', filter=Q(timestamp__gte=now - timedelta(days=7))),
            last_30_days=Count('id', filter=Q(timestamp__gte=now - timedelta(days=30))),
            failures=Count('id', filter=Q(success=False)),
        )

        def top(field):
            return list(
                AuditLog.objects.values(field)
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            )

        return Response({
            'total_audit_logs': totals['total'],
            'total_failed_events': totals['failures'],
            'total_identity_reveal_logs': IdentityRevealLog.objects.count(),
            'activity': {
                'last_24_hours': totals['last_24_hours'],
                'last_7_days': totals['last_7_days'],
                'last_30_days': totals['last_30_days'],
            },
            'event_types_breakdown': top('event_type'),
            'target_types_breakdown': top('target_type'),
        })
