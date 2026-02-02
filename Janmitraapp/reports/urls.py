"""
URL configuration for JanMitra Reports API.
"""

from django.urls import path
from .views import (
    ReportListView,
    ReportCreateView,
    ReportDetailView,
    ReportStatusView,
    JanMitraReportListView,
    AssignedReportListView,
    ReportValidateView,
    ReportRejectView,
    ReportCloseView,
)

app_name = 'reports'

urlpatterns = [
    # JanMitra endpoints
    path('my/', JanMitraReportListView.as_view(), name='my-reports'),
    path('create/', ReportCreateView.as_view(), name='report-create'),
    path('<uuid:report_id>/status/', ReportStatusView.as_view(), name='report-status'),
    
    # Authority endpoints
    path('', ReportListView.as_view(), name='report-list'),
    path('assigned/', AssignedReportListView.as_view(), name='assigned-reports'),
    path('<uuid:report_id>/', ReportDetailView.as_view(), name='report-detail'),
    path('<uuid:report_id>/validate/', ReportValidateView.as_view(), name='report-validate'),
    path('<uuid:report_id>/reject/', ReportRejectView.as_view(), name='report-reject'),
    path('<uuid:report_id>/close/', ReportCloseView.as_view(), name='report-close'),
]
