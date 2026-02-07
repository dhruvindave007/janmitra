"""
URL configuration for Core app.

Handles system-level endpoints like app version checking.
"""
from django.urls import path
from core.views import AppVersionView

app_name = 'core'

urlpatterns = [
    # App version check endpoint (public, no auth required)
    path('version/', AppVersionView.as_view(), name='app-version'),
]
