"""
URL configuration for JanMitra Escalation API.
"""

from django.urls import path
from .views import (
    EscalationListView,
    EscalationCreateView,
    EscalationDetailView,
    EscalationApproveView,
    EscalationRejectView,
    IdentityRevealRequestListView,
    IdentityRevealRequestCreateView,
    IdentityRevealRequestApproveView,
    IdentityRevealRequestRejectView,
    IdentityRevealExecuteView,
    DecryptionRequestListView,
    DecryptionRequestCreateView,
    DecryptionRequestApproveView,
    DecryptionRequestRejectView,
)

app_name = 'escalation'

urlpatterns = [
    # Escalations
    path('', EscalationListView.as_view(), name='escalation-list'),
    path('create/', EscalationCreateView.as_view(), name='escalation-create'),
    path('<uuid:escalation_id>/', EscalationDetailView.as_view(), name='escalation-detail'),
    path('<uuid:escalation_id>/approve/', EscalationApproveView.as_view(), name='escalation-approve'),
    path('<uuid:escalation_id>/reject/', EscalationRejectView.as_view(), name='escalation-reject'),
    
    # Identity reveal requests
    path('identity-reveal/', IdentityRevealRequestListView.as_view(), name='identity-reveal-list'),
    path('identity-reveal/create/', IdentityRevealRequestCreateView.as_view(), name='identity-reveal-create'),
    path('identity-reveal/<uuid:request_id>/approve/', IdentityRevealRequestApproveView.as_view(), name='identity-reveal-approve'),
    path('identity-reveal/<uuid:request_id>/reject/', IdentityRevealRequestRejectView.as_view(), name='identity-reveal-reject'),
    path('identity-reveal/<uuid:request_id>/execute/', IdentityRevealExecuteView.as_view(), name='identity-reveal-execute'),
    
    # Decryption requests
    path('decryption/', DecryptionRequestListView.as_view(), name='decryption-list'),
    path('decryption/create/', DecryptionRequestCreateView.as_view(), name='decryption-create'),
    path('decryption/<uuid:request_id>/approve/', DecryptionRequestApproveView.as_view(), name='decryption-approve'),
    path('decryption/<uuid:request_id>/reject/', DecryptionRequestRejectView.as_view(), name='decryption-reject'),
]
