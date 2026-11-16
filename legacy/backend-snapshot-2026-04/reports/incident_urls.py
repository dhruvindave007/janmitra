"""
URL configuration for JanMitra Incidents API (Case Lifecycle).

Provides endpoints for:
- Incident broadcast (JanMitra submission)
- Case listing (for Officers, Captains, Authorities)
- Case management (Authority handling)
- Level-2 case actions (notes, solve)
- Captain actions (forward, reject)

Part of the new Case Lifecycle system introduced in Step 2.
"""

from django.urls import path
from .views import (
    IncidentBroadcastView,
    AddCaseNoteView,
    SolveCaseView,
    ForwardCaseView,
    RejectCaseView,
    # List views
    CaseListView,
    OpenCasesView,
    CaseDetailView,
    JanMitraCaseListView,
    IncidentFeedView,
    # Media views
    IncidentMediaUploadView,
    IncidentMediaListView,
    IncidentMediaDownloadView,
    IncidentMediaPreviewView,
)

app_name = 'incidents'

urlpatterns = [
    # JanMitra endpoints
    path('broadcast/', IncidentBroadcastView.as_view(), name='incident-broadcast'),
    path('my/', JanMitraCaseListView.as_view(), name='janmitra-cases'),
    
    # Case listing endpoints for authorities
    path('cases/', CaseListView.as_view(), name='case-list'),
    path('cases/open/', OpenCasesView.as_view(), name='open-cases'),
    path('feed/', IncidentFeedView.as_view(), name='incident-feed'),
    
    # Case detail endpoint
    path('cases/<uuid:case_id>/', CaseDetailView.as_view(), name='case-detail'),
    
    # Level-2 case action endpoints
    path('cases/<uuid:case_id>/notes/', AddCaseNoteView.as_view(), name='case-add-note'),
    path('cases/<uuid:case_id>/solve/', SolveCaseView.as_view(), name='case-solve'),
    
    # Captain action endpoints
    path('cases/<uuid:case_id>/forward/', ForwardCaseView.as_view(), name='case-forward'),
    path('cases/<uuid:case_id>/reject/', RejectCaseView.as_view(), name='case-reject'),
    
    # Incident media endpoints
    path('<uuid:incident_id>/media/', IncidentMediaUploadView.as_view(), name='incident-media-upload'),
    path('<uuid:incident_id>/media/list/', IncidentMediaListView.as_view(), name='incident-media-list'),
    path('media/<uuid:media_id>/download/', IncidentMediaDownloadView.as_view(), name='incident-media-download'),
    path('media/<uuid:media_id>/preview/', IncidentMediaPreviewView.as_view(), name='incident-media-preview'),
]
