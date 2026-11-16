"""
URL configuration for JanMitra Media API.
"""

from django.urls import path
from .views import (
    MediaUploadView,
    MediaListView,
    MediaDetailView,
    MediaDownloadView,
)

app_name = 'media_storage'

urlpatterns = [
    # Upload media to a report
    path('upload/<uuid:report_id>/', MediaUploadView.as_view(), name='media-upload'),
    
    # List media for a report
    path('report/<uuid:report_id>/', MediaListView.as_view(), name='media-list'),
    
    # Media detail and download
    path('<uuid:media_id>/', MediaDetailView.as_view(), name='media-detail'),
    path('<uuid:media_id>/download/', MediaDownloadView.as_view(), name='media-download'),
]
