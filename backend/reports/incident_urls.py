"""
URL configuration for JanMitra Incidents API (Case Lifecycle).

Provides endpoints for:
- Incident broadcast (JanMitra submission)
- Case listing (for Officers, Captains, Authorities)
- Case management (Authority handling)
- Level-2 case actions (notes, solve)
- Captain actions (forward, reject)
- Investigation chat (messages)

Part of the new Case Lifecycle system introduced in Step 2.
"""

from django.urls import path
from .views import (
    IncidentBroadcastView,
    AddCaseNoteView,
    SolveCaseView,
    CloseCaseView,
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
    # Assignment views
    AssignCaseView,
    AvailableOfficersView,
    # Investigation chat views
    InvestigationMessagesView,
    SendMessageView,
    SendMediaMessageView,
    MessageMediaDownloadView,
    DeleteMessageView,
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
    path('cases/<uuid:case_id>/close/', CloseCaseView.as_view(), name='case-close'),
    
    # Captain action endpoints
    path('cases/<uuid:case_id>/forward/', ForwardCaseView.as_view(), name='case-forward'),
    path('cases/<uuid:case_id>/reject/', RejectCaseView.as_view(), name='case-reject'),
    
    # Assignment endpoints (L1 assigns L0)
    path('cases/<uuid:case_id>/assign/', AssignCaseView.as_view(), name='case-assign'),
    path('cases/<uuid:case_id>/officers/', AvailableOfficersView.as_view(), name='case-available-officers'),
    
    # Investigation chat endpoints
    path('cases/<uuid:case_id>/messages/', InvestigationMessagesView.as_view(), name='case-messages'),
    path('cases/<uuid:case_id>/messages/send/', SendMessageView.as_view(), name='case-send-message'),
    path('cases/<uuid:case_id>/messages/media/', SendMediaMessageView.as_view(), name='case-send-media'),
    path('messages/<uuid:message_id>/download/', MessageMediaDownloadView.as_view(), name='message-media-download'),
    path('messages/<uuid:message_id>/delete/', DeleteMessageView.as_view(), name='message-delete'),
    
    # Incident media endpoints
    path('<uuid:incident_id>/media/', IncidentMediaUploadView.as_view(), name='incident-media-upload'),
    path('<uuid:incident_id>/media/list/', IncidentMediaListView.as_view(), name='incident-media-list'),
    path('media/<uuid:media_id>/download/', IncidentMediaDownloadView.as_view(), name='incident-media-download'),
    path('media/<uuid:media_id>/preview/', IncidentMediaPreviewView.as_view(), name='incident-media-preview'),
]
