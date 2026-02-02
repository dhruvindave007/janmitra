"""
URL configuration for JanMitra Authentication API.

All authentication endpoints are under /api/v1/auth/
"""

from django.urls import path
from .views import (
    UnifiedLoginView,
    AuthorityLoginView,
    JanMitraRegistrationView,
    JanMitraLoginView,
    TokenRefreshView,
    LogoutView,
    CurrentUserView,
    InviteCodeListView,
    InviteCodeCreateView,
    RevokeUserView,
    DeviceSessionListView,
    InvalidateSessionView,
)

app_name = 'authentication'

urlpatterns = [
    # Unified login (auto-detects user type)
    path('login/', UnifiedLoginView.as_view(), name='login'),
    
    # Authority authentication
    path('authority/login/', AuthorityLoginView.as_view(), name='authority-login'),
    
    # JanMitra authentication
    path('janmitra/register/', JanMitraRegistrationView.as_view(), name='janmitra-register'),
    path('janmitra/login/', JanMitraLoginView.as_view(), name='janmitra-login'),
    
    # Token management
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # Current user
    path('me/', CurrentUserView.as_view(), name='current-user'),
    
    # Invite codes
    path('invites/', InviteCodeListView.as_view(), name='invite-list'),
    path('invites/create/', InviteCodeCreateView.as_view(), name='invite-create'),
    
    # User management
    path('users/<uuid:user_id>/revoke/', RevokeUserView.as_view(), name='user-revoke'),
    
    # Session management
    path('sessions/', DeviceSessionListView.as_view(), name='session-list'),
    path('sessions/<uuid:session_id>/invalidate/', InvalidateSessionView.as_view(), name='session-invalidate'),
]
