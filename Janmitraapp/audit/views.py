"""
Audit Views - Read-Only Access to Audit Logs

All audit logs are append-only and immutable.
Only Level 1 authorities have access to audit logs.
"""

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters import rest_framework as filters

from .models import AuditLog, IdentityRevealLog
from .serializers import AuditLogSerializer, IdentityRevealLogSerializer
from authentication.backends import DeviceBoundJWTAuthentication
from authentication.permissions import IsLevel1


class AuditLogFilter(filters.FilterSet):
    """Filter for audit logs."""
    
    action = filters.CharFilter(field_name='action', lookup_expr='iexact')
    actor = filters.UUIDFilter(field_name='actor__id')
    resource_type = filters.CharFilter(field_name='resource_type', lookup_expr='iexact')
    resource_id = filters.UUIDFilter(field_name='resource_id')
    ip_address = filters.CharFilter(field_name='ip_address', lookup_expr='exact')
    created_at_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = AuditLog
        fields = ['action', 'actor', 'resource_type', 'resource_id', 'ip_address']


class AuditLogListView(generics.ListAPIView):
    """
    List all audit logs.
    
    Only Level 1 authorities can access this endpoint.
    Audit logs are immutable - no create, update, or delete operations.
    """
    
    authentication_classes = [DeviceBoundJWTAuthentication]
    permission_classes = [IsLevel1]
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilter
    
    def get_queryset(self):
        return AuditLog.objects.all().select_related('actor').order_by('-created_at')


class AuditLogDetailView(generics.RetrieveAPIView):
    """
    Retrieve a specific audit log entry.
    
    Only Level 1 authorities can access this endpoint.
    """
    
    authentication_classes = [DeviceBoundJWTAuthentication]
    permission_classes = [IsLevel1]
    serializer_class = AuditLogSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        return AuditLog.objects.all().select_related('actor')


class IdentityRevealLogListView(generics.ListAPIView):
    """
    List all identity reveal logs.
    
    Only Level 1 authorities can access this endpoint.
    This provides a complete audit trail of all identity reveals.
    """
    
    authentication_classes = [DeviceBoundJWTAuthentication]
    permission_classes = [IsLevel1]
    serializer_class = IdentityRevealLogSerializer
    
    def get_queryset(self):
        return IdentityRevealLog.objects.all().select_related(
            'reveal_request',
            'reveal_request__report',
            'reveal_request__requested_by',
            'approved_by'
        ).order_by('-created_at')


class IdentityRevealLogDetailView(generics.RetrieveAPIView):
    """
    Retrieve a specific identity reveal log entry.
    
    Only Level 1 authorities can access this endpoint.
    """
    
    authentication_classes = [DeviceBoundJWTAuthentication]
    permission_classes = [IsLevel1]
    serializer_class = IdentityRevealLogSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        return IdentityRevealLog.objects.all().select_related(
            'reveal_request',
            'reveal_request__report',
            'reveal_request__requested_by',
            'approved_by'
        )


class AuditLogStatsView(APIView):
    """
    Get audit log statistics.
    
    Only Level 1 authorities can access this endpoint.
    """
    
    authentication_classes = [DeviceBoundJWTAuthentication]
    permission_classes = [IsLevel1]
    
    def get(self, request):
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        last_24_hours = now - timedelta(hours=24)
        last_7_days = now - timedelta(days=7)
        last_30_days = now - timedelta(days=30)
        
        # Total counts
        total_logs = AuditLog.objects.count()
        total_reveal_logs = IdentityRevealLog.objects.count()
        
        # Recent activity
        logs_24h = AuditLog.objects.filter(created_at__gte=last_24_hours).count()
        logs_7d = AuditLog.objects.filter(created_at__gte=last_7_days).count()
        logs_30d = AuditLog.objects.filter(created_at__gte=last_30_days).count()
        
        # Actions breakdown
        actions_breakdown = AuditLog.objects.values('action').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Resource types breakdown
        resource_types_breakdown = AuditLog.objects.values('resource_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return Response({
            'total_audit_logs': total_logs,
            'total_identity_reveal_logs': total_reveal_logs,
            'activity': {
                'last_24_hours': logs_24h,
                'last_7_days': logs_7d,
                'last_30_days': logs_30d,
            },
            'actions_breakdown': list(actions_breakdown),
            'resource_types_breakdown': list(resource_types_breakdown),
        })
