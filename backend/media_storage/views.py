"""
Media storage views for JanMitra Backend.

Provides REST API endpoints for:
- Encrypted media upload
- Media listing for reports
- Media metadata viewing
- Secure media download

All media is encrypted client-side before upload.
"""

import hashlib
import base64
from django.http import FileResponse
from rest_framework import status, generics, views
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser

from .models import ReportMedia, MediaType, MediaAccessLog
from reports.models import Report, ReportStatus
from authentication.permissions import (
    IsAuthenticated,
    IsJanMitra,
    IsLevel1OrLevel2,
    CanViewReport,
)
from audit.models import AuditLog, AuditEventType


class MediaUploadView(views.APIView):
    """
    Upload encrypted media to a report.
    
    POST /api/v1/media/upload/{report_id}/
    
    Request (multipart/form-data):
    - encrypted_file: The encrypted media file
    - encryption_iv: Base64-encoded IV
    - encryption_tag: Base64-encoded auth tag
    - encryption_key_id: Key identifier
    - media_type: image/video/audio/document
    - mime_type: Original MIME type
    - original_size: Original file size before encryption
    
    Only JanMitra can upload media to their own draft/submitted reports.
    """
    
    permission_classes = [IsJanMitra]
    parser_classes = [MultiPartParser]
    
    def post(self, request, report_id):
        # Get the report
        try:
            report = Report.objects.get(
                id=report_id,
                submitted_by=request.user
            )
        except Report.DoesNotExist:
            return Response(
                {'detail': 'Report not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if report can accept media
        if report.status not in [ReportStatus.DRAFT, ReportStatus.SUBMITTED]:
            return Response(
                {'detail': 'Media can only be added to draft or newly submitted reports.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate required fields
        encrypted_file = request.FILES.get('encrypted_file')
        if not encrypted_file:
            return Response(
                {'detail': 'encrypted_file is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        media_type = request.data.get('media_type')
        mime_type = request.data.get('mime_type')
        original_size = request.data.get('original_size')
        encryption_iv = request.data.get('encryption_iv')
        encryption_tag = request.data.get('encryption_tag')
        encryption_key_id = request.data.get('encryption_key_id')
        
        # Validate required fields
        if not all([media_type, mime_type, original_size, encryption_iv, encryption_tag, encryption_key_id]):
            return Response(
                {'detail': 'Missing required fields: media_type, mime_type, original_size, encryption_iv, encryption_tag, encryption_key_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate media type
        is_valid, detected_type, error = ReportMedia.validate_media_type(
            mime_type, 
            int(original_size)
        )
        if not is_valid:
            return Response(
                {'detail': error},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Decode encryption metadata
        try:
            iv_bytes = base64.b64decode(encryption_iv)
            tag_bytes = base64.b64decode(encryption_tag)
        except Exception:
            return Response(
                {'detail': 'Invalid base64 encoding for encryption metadata.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate content hash
        hasher = hashlib.sha256()
        for chunk in encrypted_file.chunks():
            hasher.update(chunk)
        content_hash = hasher.hexdigest()
        encrypted_file.seek(0)  # Reset file pointer
        
        # Create media record
        media = ReportMedia.objects.create(
            report=report,
            uploaded_by=request.user,
            encrypted_file=encrypted_file,
            encryption_iv=iv_bytes,
            encryption_tag=tag_bytes,
            encryption_key_id=encryption_key_id,
            media_type=media_type,
            mime_type=mime_type,
            file_size=encrypted_file.size,
            original_size=int(original_size),
            content_hash=content_hash,
            order=report.media_count,
        )
        
        # Update report media count
        report.media_count = report.media_files.filter(is_deleted=False).count()
        report.save(update_fields=['media_count'])
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.MEDIA_UPLOADED,
            actor=request.user,
            target=media,
            request=request,
            success=True,
            description=f"Media uploaded to report {report.report_number}",
            metadata={
                'report_number': report.report_number,
                'media_type': media_type,
                'file_size': encrypted_file.size,
                'content_hash': content_hash[:16]
            }
        )
        
        return Response({
            'id': str(media.id),
            'media_type': media.media_type,
            'file_size': media.file_size,
            'order': media.order,
            'created_at': media.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class MediaListView(views.APIView):
    """
    List media files for a report.
    
    GET /api/v1/media/report/{report_id}/
    
    Returns metadata for all media files attached to a report.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, report_id):
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return Response(
                {'detail': 'Report not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        user = request.user
        can_view = False
        
        if user.is_janmitra and report.submitted_by == user:
            can_view = True
        elif user.is_authority:
            # Level 1 can view all, Level 2 checks jurisdiction/assignment
            if user.is_level_1:
                can_view = True
            else:
                if hasattr(user, 'authority_profile'):
                    if report.jurisdiction_code == user.authority_profile.jurisdiction_code:
                        can_view = True
                if report.assigned_to == user or report.escalated_to == user:
                    can_view = True
        
        if not can_view:
            return Response(
                {'detail': 'You do not have permission to view this report\'s media.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        media_files = ReportMedia.objects.filter(report=report).order_by('order')
        
        data = []
        for media in media_files:
            data.append({
                'id': str(media.id),
                'media_type': media.media_type,
                'mime_type': media.mime_type,
                'file_size': media.file_size,
                'original_size': media.original_size,
                'order': media.order,
                'is_processed': media.is_processed,
                'is_clean': media.is_clean,
                'duration_seconds': media.duration_seconds,
                'width': media.width,
                'height': media.height,
                'created_at': media.created_at.isoformat(),
            })
        
        return Response(data)


class MediaDetailView(views.APIView):
    """
    Get media metadata.
    
    GET /api/v1/media/{media_id}/
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, media_id):
        try:
            media = ReportMedia.objects.select_related('report').get(id=media_id)
        except ReportMedia.DoesNotExist:
            return Response(
                {'detail': 'Media not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        report = media.report
        user = request.user
        
        # Permission check (same as MediaListView)
        can_view = False
        if user.is_janmitra and report.submitted_by == user:
            can_view = True
        elif user.is_level_1:
            can_view = True
        elif user.is_level_2:
            if hasattr(user, 'authority_profile'):
                if report.jurisdiction_code == user.authority_profile.jurisdiction_code:
                    can_view = True
            if report.assigned_to == user or report.escalated_to == user:
                can_view = True
        
        if not can_view:
            return Response(
                {'detail': 'You do not have permission to view this media.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Log access
        MediaAccessLog.objects.create(
            media=media,
            accessed_by_id=str(user.id),
            accessed_by_role=user.role,
            access_type='view_metadata',
            ip_address=self._get_ip(request),
            was_authorized=True,
        )
        
        return Response({
            'id': str(media.id),
            'report_id': str(report.id),
            'report_number': report.report_number,
            'media_type': media.media_type,
            'mime_type': media.mime_type,
            'file_size': media.file_size,
            'original_size': media.original_size,
            'encryption_iv_b64': base64.b64encode(media.encryption_iv).decode('utf-8'),
            'encryption_tag_b64': base64.b64encode(media.encryption_tag).decode('utf-8'),
            'encryption_key_id': media.encryption_key_id,
            'content_hash': media.content_hash,
            'order': media.order,
            'is_processed': media.is_processed,
            'is_clean': media.is_clean,
            'duration_seconds': media.duration_seconds,
            'width': media.width,
            'height': media.height,
            'created_at': media.created_at.isoformat(),
        })
    
    def _get_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class MediaDownloadView(views.APIView):
    """
    Download encrypted media file.
    
    GET /api/v1/media/{media_id}/download/
    
    Returns the encrypted file for authorized users.
    For decryption, the client needs the encryption key.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, media_id):
        try:
            media = ReportMedia.objects.select_related('report').get(id=media_id)
        except ReportMedia.DoesNotExist:
            return Response(
                {'detail': 'Media not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        report = media.report
        user = request.user
        
        # Permission check
        can_download = False
        authorization_id = ''
        
        if user.is_janmitra and report.submitted_by == user:
            can_download = True
        elif user.is_level_1:
            can_download = True
        elif user.is_level_2:
            # Level 2 needs decryption authorization for assigned reports
            if report.decryption_authorized:
                if report.assigned_to == user or report.escalated_to == user:
                    can_download = True
                    # Get authorization ID from report
                    if report.decryption_authorized_by:
                        authorization_id = str(report.decryption_authorized_by.id)
        
        if not can_download:
            return Response(
                {'detail': 'You do not have permission to download this media. Decryption authorization may be required.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Log download access
        MediaAccessLog.objects.create(
            media=media,
            accessed_by_id=str(user.id),
            accessed_by_role=user.role,
            access_type='download',
            ip_address=self._get_ip(request),
            was_authorized=True,
            authorization_id=authorization_id,
        )
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.MEDIA_ACCESSED,
            actor=user,
            target=media,
            request=request,
            success=True,
            description=f"Media downloaded for report {report.report_number}",
            metadata={
                'report_number': report.report_number,
                'media_type': media.media_type,
            }
        )
        
        # Return file
        response = FileResponse(
            media.encrypted_file.open('rb'),
            content_type='application/octet-stream'
        )
        response['Content-Disposition'] = f'attachment; filename="{media.id}.enc"'
        response['Content-Length'] = media.file_size
        
        return response
    
    def _get_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
