"""
URL configuration for JanMitra Audit API.
"""

from django.urls import path
from .views import (
    AuditLogListView,
    AuditLogDetailView,
    IdentityRevealLogListView,
    IdentityRevealLogDetailView,
    AuditLogStatsView,
)

app_name = 'audit'

urlpatterns = [
    # Audit logs (Level 1 only)
    path('logs/', AuditLogListView.as_view(), name='audit-log-list'),
    path('logs/stats/', AuditLogStatsView.as_view(), name='audit-log-stats'),
    path('logs/<uuid:id>/', AuditLogDetailView.as_view(), name='audit-log-detail'),
    
    # Identity reveal logs (Level 1 only, critical)
    path('identity-reveals/', IdentityRevealLogListView.as_view(), name='identity-reveal-log-list'),
    path('identity-reveals/<uuid:id>/', IdentityRevealLogDetailView.as_view(), name='identity-reveal-log-detail'),
]
