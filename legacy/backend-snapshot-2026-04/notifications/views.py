"""
Notification views for JanMitra Backend.

Provides API endpoints for:
- List user notifications
- Get notification detail
- Mark notification as read
- Mark all as read
- Get unread count
"""

from rest_framework import generics, views, status
from rest_framework.response import Response

from authentication.permissions import IsAuthenticated, IsLevel1OrLevel2
from .models import Notification
from .serializers import NotificationSerializer, NotificationListSerializer, UnreadCountSerializer
from .services import NotificationService


class NotificationListView(generics.ListAPIView):
    """
    List notifications for the authenticated user.
    
    GET /api/v1/notifications/
    
    Query parameters:
    - is_read: Filter by read status (true/false)
    - type: Filter by notification type
    
    Returns: Paginated list of notifications, newest first.
    """
    
    permission_classes = [IsLevel1OrLevel2]
    serializer_class = NotificationListSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(recipient=user)
        
        # Optional filters
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        notification_type = self.request.query_params.get('type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        return queryset.order_by('-created_at')


class NotificationDetailView(generics.RetrieveAPIView):
    """
    Get a single notification detail.
    
    GET /api/v1/notifications/{id}/
    
    User can only view their own notifications.
    """
    
    permission_classes = [IsLevel1OrLevel2]
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class MarkNotificationReadView(views.APIView):
    """
    Mark a notification as read.
    
    POST /api/v1/notifications/{id}/read/
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def post(self, request, pk):
        try:
            notification = Notification.objects.get(
                id=pk,
                recipient=request.user
            )
        except Notification.DoesNotExist:
            return Response(
                {'detail': 'Notification not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        notification.mark_as_read()
        
        return Response({
            'id': str(notification.id),
            'is_read': notification.is_read,
            'read_at': notification.read_at.isoformat() if notification.read_at else None,
        })


class MarkAllReadView(views.APIView):
    """
    Mark all notifications as read for the authenticated user.
    
    POST /api/v1/notifications/read-all/
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def post(self, request):
        count = NotificationService.mark_all_read(request.user)
        
        return Response({
            'message': f'Marked {count} notifications as read.',
            'count': count,
        })


class UnreadCountView(views.APIView):
    """
    Get count of unread notifications.
    
    GET /api/v1/notifications/unread-count/
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def get(self, request):
        count = NotificationService.get_unread_count(request.user)
        
        return Response({
            'unread_count': count,
        })

