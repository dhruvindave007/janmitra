"""
URL configuration for core app.

Public endpoints:
- /api/v1/app/version-check/  — Mobile app version check (no auth)
"""

from django.urls import path
from .views import version_check

app_name = 'core'

urlpatterns = [
    path('version-check/', version_check, name='version-check'),
]
