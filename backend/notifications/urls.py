"""
URL configuration for notifications.
"""

from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    # List notifications
    path('', views.NotificationListView.as_view(), name='list'),
    
    # Unread count
    path('unread-count/', views.UnreadCountView.as_view(), name='unread-count'),
    
    # Mark all as read
    path('read-all/', views.MarkAllReadView.as_view(), name='read-all'),
    
    # Single notification detail
    path('<uuid:pk>/', views.NotificationDetailView.as_view(), name='detail'),
    
    # Mark single notification as read
    path('<uuid:pk>/read/', views.MarkNotificationReadView.as_view(), name='mark-read'),
]
