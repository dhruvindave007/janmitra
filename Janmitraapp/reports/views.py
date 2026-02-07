"""
Report views for JanMitra Backend.

Provides REST API endpoints for:
- Report creation (JanMitra)
- Report listing (based on role)
- Report status viewing
- Report validation/rejection (Level 2)
- Report closure (Level 1/2)

All operations are audited.
"""

from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from datetime import timedelta

import logging
from rest_framework import status, generics, views
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
logger = logging.getLogger(__name__)

from .models import (
    Report, ReportStatus, ReportStatusHistory,
    Incident, Case, CaseNote, CaseStatusHistory, CaseStatus, CaseLevel, IncidentCategory,
    IncidentMedia, IncidentMediaType,
)
from .serializers import (
    ReportCreateSerializer,
    ReportDetailSerializer,
    ReportListSerializer,
    ReportStatusSerializer,
    JanMitraReportSerializer,
    ReportValidateSerializer,
    ReportRejectSerializer,
)
from authentication.permissions import (
    IsAuthenticated,
    IsJanMitra,
    IsLevel1OrLevel2,
    IsLevel1,
    CanViewReport,
    CanModifyReport,
)
from audit.models import AuditLog, AuditEventType
from notifications.services import NotificationService
from .services import LocationResolverService


class ReportCreateView(views.APIView):
    """
    Create a new encrypted report.
    
    POST /api/v1/reports/create/
    
    Request:
    {
        "encrypted_title": "base64_encrypted_data",
        "encrypted_content": "base64_encrypted_data",
        "encryption_iv": "base64_iv",
        "encryption_tag": "base64_tag",
        "encryption_key_id": "key_identifier",
        "category": "public_safety",
        "priority": "medium",
        "jurisdiction_code": "ZONE-001",
        "location_zone": "Downtown Area",
        "incident_timestamp": "2024-01-15T10:30:00Z"
    }
    
    Only JanMitra members can create reports.
    """
    
    permission_classes = [IsJanMitra]
    serializer_class = ReportCreateSerializer
    
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.REPORT_CREATED,
            actor=request.user,
            target=report,
            request=request,
            success=True,
            description=f"Report created: {report.report_number}",
            metadata={
                'report_number': report.report_number,
                'category': report.category,
                'priority': report.priority
            }
        )
        
        return Response(
            JanMitraReportSerializer(report).data,
            status=status.HTTP_201_CREATED
        )


class JanMitraReportListView(generics.ListAPIView):
    """
    List reports submitted by the current JanMitra member.
    
    GET /api/v1/reports/my/
    
    JanMitra members can only see their own reports with limited details.
    """
    
    permission_classes = [IsJanMitra]
    serializer_class = JanMitraReportSerializer
    
    def get_queryset(self):
        return Report.objects.filter(
            submitted_by=self.request.user
        ).order_by('-submitted_at')


class ReportStatusView(views.APIView):
    """
    Get status of a specific report (JanMitra view).
    
    GET /api/v1/reports/{report_id}/status/
    
    Returns limited status information for JanMitra members.
    """
    
    permission_classes = [IsJanMitra]
    
    def get(self, request, report_id):
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
        
        # Log access
        AuditLog.log(
            event_type=AuditEventType.REPORT_VIEWED,
            actor=request.user,
            target=report,
            request=request,
            success=True,
            description="JanMitra viewed report status"
        )
        
        return Response(ReportStatusSerializer(report).data)


class ReportListView(generics.ListAPIView):
    """
    List reports for authorities.
    
    GET /api/v1/reports/
    
    - Level 1 sees all reports
    - Level 2 sees reports in their jurisdiction
    
    Query parameters:
    - status: Filter by status
    - priority: Filter by priority
    - category: Filter by category
    - jurisdiction_code: Filter by jurisdiction
    """
    
    permission_classes = [IsLevel1OrLevel2]
    serializer_class = ReportListSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Report.objects.all()
        
        # Level 2 sees only their jurisdiction
        if user.is_level_2:
            if hasattr(user, 'authority_profile'):
                queryset = queryset.filter(
                    Q(jurisdiction_code=user.authority_profile.jurisdiction_code) |
                    Q(assigned_to=user) |
                    Q(escalated_to=user)
                )
            else:
                queryset = queryset.filter(assigned_to=user)
        
        # Apply filters
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        priority_filter = self.request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        category_filter = self.request.query_params.get('category')
        if category_filter:
            queryset = queryset.filter(category=category_filter)
        
        jurisdiction_filter = self.request.query_params.get('jurisdiction_code')
        if jurisdiction_filter:
            queryset = queryset.filter(jurisdiction_code=jurisdiction_filter)
        
        return queryset.order_by('-submitted_at')


class AssignedReportListView(generics.ListAPIView):
    """
    List reports assigned to the current authority.
    
    GET /api/v1/reports/assigned/
    """
    
    permission_classes = [IsLevel1OrLevel2]
    serializer_class = ReportListSerializer
    
    def get_queryset(self):
        return Report.objects.filter(
            Q(assigned_to=self.request.user) |
            Q(escalated_to=self.request.user)
        ).exclude(
            status__in=ReportStatus.TERMINAL_STATES
        ).order_by('-submitted_at')


class ReportDetailView(views.APIView):
    """
    Get detailed report information.
    
    GET /api/v1/reports/{report_id}/
    
    Authorities can view report details.
    Encrypted content is returned but not decrypted unless authorized.
    """
    
    permission_classes = [IsLevel1OrLevel2, CanViewReport]
    
    def get(self, request, report_id):
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return Response(
                {'detail': 'Report not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check object-level permissions
        self.check_object_permissions(request, report)
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.REPORT_VIEWED,
            actor=request.user,
            target=report,
            request=request,
            success=True,
            description=f"Authority viewed report: {report.report_number}",
            metadata={
                'report_number': report.report_number,
                'viewer_role': request.user.role
            }
        )
        
        serializer = ReportDetailSerializer(
            report,
            context={'request': request}
        )
        return Response(serializer.data)


class ReportValidateView(views.APIView):
    """
    Validate a report (mark as credible).
    
    POST /api/v1/reports/{report_id}/validate/
    
    Request:
    {
        "notes": "Validation notes"
    }
    """
    
    permission_classes = [IsLevel1OrLevel2, CanModifyReport]
    serializer_class = ReportValidateSerializer
    
    def post(self, request, report_id):
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return Response(
                {'detail': 'Report not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        self.check_object_permissions(request, report)
        
        # Validate status transition
        if report.status in ReportStatus.TERMINAL_STATES:
            return Response(
                {'detail': 'Report is already in a terminal state.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Record status change
        old_status = report.status
        report.status = ReportStatus.VALIDATED
        report.save()
        
        # Create status history
        ReportStatusHistory.objects.create(
            report=report,
            from_status=old_status,
            to_status=ReportStatus.VALIDATED,
            changed_by=request.user,
            reason=serializer.validated_data.get('notes', '')
        )
        
        # Update JanMitra trust score
        if hasattr(report.submitted_by, 'janmitra_profile'):
            report.submitted_by.janmitra_profile.increment_report_count('verified')
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.REPORT_VALIDATED,
            actor=request.user,
            target=report,
            request=request,
            success=True,
            description=f"Report validated: {report.report_number}",
            metadata={
                'report_number': report.report_number,
                'previous_status': old_status
            }
        )
        
        return Response({'detail': 'Report validated successfully.'})


class ReportRejectView(views.APIView):
    """
    Reject a report.
    
    POST /api/v1/reports/{report_id}/reject/
    
    Request:
    {
        "reason": "Rejection reason",
        "rejection_type": "invalid"  # invalid, duplicate, rejected
    }
    """
    
    permission_classes = [IsLevel1OrLevel2, CanModifyReport]
    serializer_class = ReportRejectSerializer
    
    def post(self, request, report_id):
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return Response(
                {'detail': 'Report not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        self.check_object_permissions(request, report)
        
        if report.status in ReportStatus.TERMINAL_STATES:
            return Response(
                {'detail': 'Report is already in a terminal state.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Determine rejection status
        rejection_type = serializer.validated_data.get('rejection_type', 'rejected')
        new_status = {
            'invalid': ReportStatus.INVALID,
            'duplicate': ReportStatus.DUPLICATE,
            'rejected': ReportStatus.REJECTED,
        }.get(rejection_type, ReportStatus.REJECTED)
        
        # Record status change
        old_status = report.status
        report.status = new_status
        report.save()
        
        # Create status history
        ReportStatusHistory.objects.create(
            report=report,
            from_status=old_status,
            to_status=new_status,
            changed_by=request.user,
            reason=serializer.validated_data.get('reason', '')
        )
        
        # Update JanMitra trust score
        if hasattr(report.submitted_by, 'janmitra_profile'):
            report.submitted_by.janmitra_profile.increment_report_count('rejected')
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.REPORT_REJECTED,
            actor=request.user,
            target=report,
            request=request,
            success=True,
            description=f"Report rejected: {report.report_number}",
            metadata={
                'report_number': report.report_number,
                'rejection_type': rejection_type,
                'reason': serializer.validated_data.get('reason', '')
            }
        )
        
        return Response({'detail': 'Report rejected.'})


class ReportCloseView(views.APIView):
    """
    Close a report.
    
    POST /api/v1/reports/{report_id}/close/
    
    Request:
    {
        "resolution_notes": "Final resolution notes"
    }
    """
    
    permission_classes = [IsLevel1OrLevel2, CanModifyReport]
    
    def post(self, request, report_id):
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return Response(
                {'detail': 'Report not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        self.check_object_permissions(request, report)
        
        if report.status in ReportStatus.TERMINAL_STATES:
            return Response(
                {'detail': 'Report is already closed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        resolution_notes = request.data.get('resolution_notes', '')
        
        # Close the report
        old_status = report.status
        report.close(request.user, resolution_notes)
        
        # Create status history
        ReportStatusHistory.objects.create(
            report=report,
            from_status=old_status,
            to_status=ReportStatus.CLOSED,
            changed_by=request.user,
            reason=resolution_notes
        )
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.REPORT_STATUS_CHANGED,
            actor=request.user,
            target=report,
            request=request,
            success=True,
            description=f"Report closed: {report.report_number}",
            metadata={
                'report_number': report.report_number,
                'previous_status': old_status
            }
        )
        
        return Response({'detail': 'Report closed successfully.'})


# =============================================================================
# INCIDENT / CASE LIFECYCLE VIEWS (Step 2)
# =============================================================================

class IncidentBroadcastView(views.APIView):
    """
    Broadcast an incident from JanMitra app.
    
    POST /api/v1/incidents/broadcast/
    
    Request (multipart/form-data or JSON):
    {
        "text_content": "Incident description",
        "category": "public_safety",
        "latitude": 12.9716,  (optional)
        "longitude": 77.5946,  (optional)
        "media_files": [file1, file2, file3]  (optional, max 3)
    }
    
    Creates an Incident (immutable), a Case (for lifecycle tracking),
    and IncidentMedia records for any uploaded files.
    """
    
    # Accept any authenticated user to broadcast incidents (JanMitra flag not required)
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def post(self, request):
        # Validate required fields
        text_content = request.data.get('text_content', '').strip()
        if not text_content:
            return Response(
                {'text_content': ['This field is required.']},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        category = request.data.get('category', IncidentCategory.GENERAL)
        if category not in dict(IncidentCategory.CHOICES):
            category = IncidentCategory.GENERAL
        
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        # Area metadata (resolved from frontend geocoding)
        area_name = request.data.get('area_name', '').strip() or None
        city = request.data.get('city', '').strip() or None
        state = request.data.get('state', '').strip() or None
        
        # Enforce max length of 255 for area fields
        if area_name and len(area_name) > 255:
            area_name = area_name[:255]
        if city and len(city) > 255:
            city = city[:255]
        if state and len(state) > 255:
            state = state[:255]
        
        # Use transaction to ensure Incident + Case are created atomically
        with transaction.atomic():
            # Create the Incident (immutable submission)
            incident = Incident.objects.create(
                submitted_by=request.user,
                text_content=text_content,
                category=category,
                latitude=latitude,
                longitude=longitude,
                area_name=area_name,
                city=city,
                state=state,
            )
            
            # Create the Case (lifecycle tracking)
            # Default SLA: 24 hours for Level 2
            sla_deadline = timezone.now() + timedelta(hours=24)
            
            case = Case.objects.create(
                incident=incident,
                current_level=CaseLevel.LEVEL_2,
                status=CaseStatus.OPEN,
                sla_deadline=sla_deadline,
            )
            
            # Create initial status history
            CaseStatusHistory.objects.create(
                case=case,
                from_status=None,
                to_status=CaseStatus.OPEN,
                from_level=None,
                to_level=CaseLevel.LEVEL_2,
                changed_by=request.user,
                reason="Initial submission"
            )
        
        # Handle media file uploads (outside main transaction for atomicity)
        # Media upload failure should NOT fail the incident creation
        media_uploaded = 0
        media_errors = []
        media_files = request.FILES.getlist('media_files')
        
        if media_files:
            import os
            for uploaded_file in media_files[:IncidentMediaType.MAX_FILES_PER_INCIDENT]:
                try:
                    # Determine media type from extension
                    ext = os.path.splitext(uploaded_file.name)[1].lower()
                    media_type = None
                    for mtype, extensions in IncidentMediaType.ALLOWED_EXTENSIONS.items():
                        if ext in extensions:
                            media_type = mtype
                            break
                    
                    if media_type is None:
                        media_errors.append(f"Invalid file type: {uploaded_file.name}")
                        continue
                    
                    # Check file size
                    max_size = IncidentMediaType.MAX_SIZES.get(media_type, 10 * 1024 * 1024)
                    if uploaded_file.size > max_size:
                        media_errors.append(f"File too large: {uploaded_file.name}")
                        continue
                    
                    # Create IncidentMedia record
                    IncidentMedia.objects.create(
                        incident=incident,
                        file=uploaded_file,
                        media_type=media_type,
                        original_filename=uploaded_file.name,
                        file_size=uploaded_file.size,
                        content_type=getattr(uploaded_file, 'content_type', ''),
                        uploaded_by=request.user,
                    )
                    media_uploaded += 1
                except Exception as e:
                    media_errors.append(f"Failed to save {uploaded_file.name}: {str(e)}")
        
        # Notify Level 2 authorities about the new case (outside transaction - non-critical)
        try:
            NotificationService.notify_new_case(case)
        except Exception:
            pass  # Non-critical - don't fail the request
        
        # Resolve area name from GPS coordinates asynchronously (outside transaction - non-critical)
        # This enriches incident with geographic metadata for better case routing
        if incident.latitude and incident.longitude and not incident.area_name:
            try:
                resolved_area = LocationResolverService.resolve_area_name(
                    incident.latitude,
                    incident.longitude
                )
                if resolved_area:
                    incident.area_name = resolved_area
                    incident.save(update_fields=['area_name'])
                    logger.info(f"[IncidentBroadcast] Area resolved for incident {incident.id}: {resolved_area}")
            except Exception as e:
                logger.warning(f"[IncidentBroadcast] Location resolution failed: {e}")
                pass  # Non-critical - don't fail the request
        
        # Audit log (outside transaction - non-critical)
        AuditLog.log(
            event_type=AuditEventType.REPORT_CREATED,
            actor=request.user,
            target=incident,
            request=request,
            success=True,
            description=f"Incident broadcast: {incident.id}",
            metadata={
                'incident_id': str(incident.id),
                'case_id': str(case.id),
                'category': category,
                'media_uploaded': media_uploaded,
                'media_errors': media_errors,
            }
        )
        
        response_data = {
            'message': 'Incident broadcast received',
            'incident_id': str(incident.id),
            'case_id': str(case.id),
            'media_uploaded': media_uploaded,
        }
        if media_errors:
            response_data['media_errors'] = media_errors
        
        return Response(response_data, status=status.HTTP_201_CREATED)


class AddCaseNoteView(views.APIView):
    """
    Add a note to a case.
    
    POST /api/v1/incidents/{case_id}/notes/
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def post(self, request, case_id):
        try:
            case = Case.objects.get(id=case_id, is_deleted=False)
        except Case.DoesNotExist:
            return Response(
                {'detail': 'Case not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        content = request.data.get('content', '').strip()
        if not content:
            return Response(
                {'content': ['This field is required.']},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine author's level
        user = request.user
        if hasattr(user, 'role'):
            author_level = user.role.upper()
        else:
            author_level = 'LEVEL_2'
        
        note = CaseNote.objects.create(
            case=case,
            author=user,
            author_level=author_level,
            note_text=content,
        )
        
        return Response({
            'id': str(note.id),
            'content': note.note_text,
            'author_level': note.author_level,
            'created_at': note.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class SolveCaseView(views.APIView):
    """
    Mark a case as solved.
    
    POST /api/v1/incidents/{case_id}/solve/
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def post(self, request, case_id):
        try:
            case = Case.objects.get(id=case_id, is_deleted=False)
        except Case.DoesNotExist:
            return Response(
                {'detail': 'Case not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if case.status != CaseStatus.OPEN:
            return Response(
                {'detail': 'Case is not open.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        solution_notes = request.data.get('solution_notes', '')
        
        old_status = case.status
        case.status = CaseStatus.SOLVED
        case.solved_at = timezone.now()
        case.solved_by = request.user
        case.solution_notes = solution_notes
        case.save()
        
        # Status history
        CaseStatusHistory.objects.create(
            case=case,
            from_status=old_status,
            to_status=CaseStatus.SOLVED,
            changed_by=request.user,
            reason=solution_notes
        )
        
        # Notify relevant authorities about the solution
        try:
            NotificationService.notify_case_solved(case, request.user)
        except Exception:
            pass  # Non-critical
        
        return Response({'detail': 'Case marked as solved.'})


class ForwardCaseView(views.APIView):
    """
    Forward (escalate) a case to higher level.
    
    POST /api/v1/incidents/{case_id}/forward/
    
    Only Level 2 Captain can forward.
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def post(self, request, case_id):
        try:
            case = Case.objects.get(id=case_id, is_deleted=False)
        except Case.DoesNotExist:
            return Response(
                {'detail': 'Case not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if case.status != CaseStatus.OPEN:
            return Response(
                {'detail': 'Case is not open.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if case.current_level <= CaseLevel.LEVEL_0:
            return Response(
                {'detail': 'Case is already at highest level.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        
        old_level = case.current_level
        case.current_level = old_level - 1
        case.escalation_count += 1
        case.last_escalated_at = timezone.now()
        # Reset SLA for new level
        case.sla_deadline = timezone.now() + timedelta(hours=24)
        case.save()
        
        # Status history
        CaseStatusHistory.objects.create(
            case=case,
            from_status=case.status,
            to_status=case.status,
            from_level=old_level,
            to_level=case.current_level,
            changed_by=request.user,
            reason=reason or "Forwarded to higher level"
        )
        
        # Notify authorities about the escalation
        try:
            NotificationService.notify_case_escalated(
                case=case,
                from_level=old_level,
                to_level=case.current_level,
                escalated_by=request.user,
                reason=reason or "Forwarded to higher level"
            )
        except Exception:
            pass  # Non-critical
        
        return Response({'detail': f'Case forwarded to Level {case.current_level}.'})


class RejectCaseView(views.APIView):
    """
    Reject a case.
    
    POST /api/v1/incidents/{case_id}/reject/
    
    Only Level 2 Captain can reject.
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def post(self, request, case_id):
        try:
            case = Case.objects.get(id=case_id, is_deleted=False)
        except Case.DoesNotExist:
            return Response(
                {'detail': 'Case not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if case.status != CaseStatus.OPEN:
            return Response(
                {'detail': 'Case is not open.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        if not reason:
            return Response(
                {'reason': ['Rejection reason is required.']},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_status = case.status
        case.status = CaseStatus.REJECTED
        case.rejected_at = timezone.now()
        case.rejected_by = request.user
        case.rejection_reason = reason
        case.save()
        
        # Status history
        CaseStatusHistory.objects.create(
            case=case,
            from_status=old_status,
            to_status=CaseStatus.REJECTED,
            changed_by=request.user,
            reason=reason
        )
        
        # Notify authorities about the rejection
        try:
            NotificationService.notify_case_rejected(case, request.user, reason)
        except Exception:
            pass  # Non-critical
        
        return Response({'detail': 'Case rejected.'})

# =============================================================================
# CASE LIST VIEWS (for Officers, Captains, Authorities)
# =============================================================================

from .serializers import CaseListSerializer, CaseDetailSerializer, JanMitraCaseSerializer


class CaseListView(generics.ListAPIView):
    """
    List cases for authorities based on their role and level.
    
    GET /api/v1/incidents/cases/
    
    STRICT VISIBILITY RULES:
    - JanMitra: NEVER sees case list (403 Forbidden)
    - Level-2 Officer: sees ONLY current_level=2 cases
    - Level-2 Captain: sees current_level=2 cases (can see escalated read-only)
    - Level-1 Authority: sees ONLY current_level=1 cases
    - Level-0 Authority: sees ONLY current_level=0 cases
    
    Query parameters:
    - status: Filter by status (open, solved, rejected)
    """
    
    permission_classes = [IsLevel1OrLevel2]
    serializer_class = CaseListSerializer
    
    def get_queryset(self):
        from .models import visible_cases_for_user
        user = self.request.user
        if getattr(user, 'is_janmitra', False):
            return Case.objects.none()
        queryset = visible_cases_for_user(user)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset.order_by('-created_at')


class OpenCasesView(generics.ListAPIView):
    """
    List OPEN cases for field officers (quick dashboard view).
    
    GET /api/v1/incidents/cases/open/
    
    Same visibility rules as CaseListView, but filtered to OPEN status only.
    Sorted by SLA deadline (most urgent first).
    """
    
    permission_classes = [IsLevel1OrLevel2]
    serializer_class = CaseListSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # JanMitra should NEVER access this endpoint
        if user.is_janmitra:
            return Case.objects.none()
        
        queryset = Case.objects.select_related('incident', 'incident__submitted_by').filter(
            is_deleted=False,
            status=CaseStatus.OPEN
        )
        
        # STRICT role-based filtering
        if user.is_level_2 and not user.is_level_2_captain:
            queryset = queryset.filter(current_level=CaseLevel.LEVEL_2)
        elif user.is_level_2_captain:
            queryset = queryset.filter(current_level__lte=CaseLevel.LEVEL_2)
        elif user.is_level_1:
            queryset = queryset.filter(current_level=CaseLevel.LEVEL_1)
        elif user.is_level_0:
            queryset = queryset.filter(current_level=CaseLevel.LEVEL_0)
        else:
            return Case.objects.none()
        
        return queryset.order_by('sla_deadline')  # Most urgent first


class CaseDetailView(views.APIView):
    """
    Get full case details.
    
    GET /api/v1/incidents/cases/{case_id}/
    
    Enforces same visibility rules as CaseListView.
    Returns 404 if case is not at user's visible level.
    """
    
    permission_classes = [IsLevel1OrLevel2]
    

    def get_queryset(self):
        from .models import visible_cases_for_user
        user = self.request.user
        if getattr(user, 'is_janmitra', False):
            return Case.objects.none()
        return visible_cases_for_user(user).select_related('incident', 'incident__submitted_by').prefetch_related('incident__media_files', 'notes', 'notes__author')

    def get(self, request, case_id):
        from django.shortcuts import get_object_or_404
        queryset = self.get_queryset()
        case = get_object_or_404(queryset, id=case_id)
        serializer = CaseDetailSerializer(case, context={'request': request})
        data = serializer.data
        if 'media_files' not in data or not data['media_files']:
            data['media_files'] = []
        if 'notes' not in data or not data['notes']:
            data['notes'] = []
        return Response(data)


class JanMitraCaseListView(generics.ListAPIView):
    """
    DEPRECATED: JanMitra members should NOT see case history.
    
    GET /api/v1/incidents/my/
    
    Per business rules, JanMitra users can ONLY broadcast incidents.
    They cannot view case lists, status, or history.
    This endpoint returns empty results.
    """
    
    permission_classes = [IsJanMitra]
    serializer_class = JanMitraCaseSerializer
    
    def get_queryset(self):
        # JanMitra should NOT see case history per business rules
        # Return empty queryset
        return Case.objects.none()


class IncidentFeedView(generics.ListAPIView):
    """
    Incident feed for authorities (newest first).
    
    GET /api/v1/incidents/feed/
    
    Same visibility rules as CaseListView.
    Shows incidents/cases that the user is allowed to see.
    """
    
    permission_classes = [IsLevel1OrLevel2]
    serializer_class = CaseListSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # JanMitra should NEVER access this endpoint
        if user.is_janmitra:
            return Case.objects.none()
        
        queryset = Case.objects.select_related('incident', 'incident__submitted_by').filter(
            is_deleted=False
        )
        
        # STRICT role-based filtering
        if user.is_level_2 and not user.is_level_2_captain:
            queryset = queryset.filter(current_level=CaseLevel.LEVEL_2)
        elif user.is_level_2_captain:
            queryset = queryset.filter(current_level__lte=CaseLevel.LEVEL_2)
        elif user.is_level_1:
            queryset = queryset.filter(current_level=CaseLevel.LEVEL_1)
        elif user.is_level_0:
            queryset = queryset.filter(current_level=CaseLevel.LEVEL_0)
        else:
            return Case.objects.none()
        
        return queryset.order_by('-created_at')[:100]  # Last 100 incidents


# =============================================================================
# INCIDENT MEDIA VIEWS
# =============================================================================

from django.http import FileResponse, Http404
from .serializers import IncidentMediaSerializer, IncidentMediaUploadSerializer


class IncidentMediaUploadView(views.APIView):
    """
    Upload media to an incident.
    
    POST /api/v1/incidents/{incident_id}/media/
    
    Rules:
    - JanMitra ONLY can upload
    - Maximum 3 files per incident
    - Only photo/video allowed
    - File size limits enforced
    """
    
    permission_classes = [IsJanMitra]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, incident_id):
        # Get the incident
        try:
            incident = Incident.objects.get(id=incident_id, is_deleted=False)
        except Incident.DoesNotExist:
            return Response(
                {'detail': 'Incident not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify ownership - only submitter can upload media
        if incident.submitted_by != request.user:
            return Response(
                {'detail': 'You can only upload media to your own incidents.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate the upload
        serializer = IncidentMediaUploadSerializer(
            data=request.data,
            context={'incident': incident, 'request': request}
        )
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = serializer.validated_data['file']
        
        # Create the media record
        media = IncidentMedia.objects.create(
            incident=incident,
            file=uploaded_file,
            media_type=uploaded_file.detected_media_type,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            content_type=getattr(uploaded_file, 'content_type', ''),
            uploaded_by=request.user,
        )
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.MEDIA_UPLOADED,
            actor=request.user,
            target=media,
            request=request,
            success=True,
            description=f"Media uploaded to incident {incident_id}",
            metadata={
                'incident_id': str(incident_id),
                'media_id': str(media.id),
                'media_type': media.media_type,
                'file_size': media.file_size,
                'original_filename': media.original_filename,
            }
        )
        
        return Response({
            'id': str(media.id),
            'media_type': media.media_type,
            'file_size': media.file_size,
            'created_at': media.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class IncidentMediaListView(views.APIView):
    """
    List media for an incident.
    
    GET /api/v1/incidents/{incident_id}/media/
    
    Rules:
    - Level-2+ authorities: READ access
    - JanMitra: NO access after submission
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def get(self, request, incident_id):
        # Get the incident
        try:
            incident = Incident.objects.get(id=incident_id, is_deleted=False)
        except Incident.DoesNotExist:
            return Response(
                {'detail': 'Incident not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get media files
        media_files = IncidentMedia.objects.filter(
            incident=incident,
            is_deleted=False
        ).order_by('created_at')
        
        serializer = IncidentMediaSerializer(media_files, many=True)
        return Response(serializer.data)


class IncidentMediaDownloadView(views.APIView):
    """
    Download a specific media file.
    
    GET /api/v1/incidents/media/{media_id}/download/
    
    Rules:
    - Level-0 (Super Admin): CAN download
    - Level-1 (Senior Authority): CAN download
    - Level-2 Captain: CAN download
    - Level-2 (Field Authority): CANNOT download - return 403
    - JanMitra: NO access - return 403
    
    Returns file with proper content-type.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, media_id):
        from authentication.models import UserRole
        
        user = request.user
        
        # Check role-based access
        # JanMitra: NO access at all
        if user.is_janmitra:
            return Response(
                {'detail': 'JanMitra users cannot access media files.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Level-2 officers (not captains): CANNOT download
        if user.role == UserRole.LEVEL_2:
            return Response(
                {
                    'detail': 'Level-2 officers cannot download media files. Preview only.',
                    'code': 'download_restricted'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Allowed roles: LEVEL_0, LEVEL_1, LEVEL_2_CAPTAIN
        allowed_roles = [UserRole.LEVEL_0, UserRole.LEVEL_1, UserRole.LEVEL_2_CAPTAIN]
        if user.role not in allowed_roles:
            return Response(
                {'detail': 'You do not have permission to download media files.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get the media file
        try:
            media = IncidentMedia.objects.select_related('incident').get(
                id=media_id,
                is_deleted=False
            )
        except IncidentMedia.DoesNotExist:
            return Response(
                {'detail': 'Media not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if file exists
        if not media.file:
            raise Http404("File not found")
        
        # Audit log for media access
        AuditLog.log(
            event_type=AuditEventType.MEDIA_ACCESSED,
            actor=request.user,
            target=media,
            request=request,
            success=True,
            description=f"Media downloaded: {media_id}",
            metadata={
                'media_id': str(media_id),
                'incident_id': str(media.incident_id),
                'media_type': media.media_type,
                'access_type': 'download',
            }
        )
        
        # Return file response
        response = FileResponse(
            media.file.open('rb'),
            content_type=media.content_type or 'application/octet-stream'
        )
        
        # Set filename for download
        filename = media.original_filename or f"media_{media_id}"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


class IncidentMediaPreviewView(views.APIView):
    """
    Get a preview/thumbnail of a media file.
    
    GET /api/v1/incidents/media/{media_id}/preview/
    
    Returns:
    - For images: Low-res version (max 400px)
    - For videos: First frame as image
    
    Rules:
    - All authority roles (Level-0, Level-1, Level-2 Captain, Level-2): CAN preview
    - JanMitra: NO access
    
    This allows Level-2 officers to see previews without download capability.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, media_id):
        from PIL import Image
        from io import BytesIO
        import os
        
        user = request.user
        
        # JanMitra: NO access
        if user.is_janmitra:
            return Response(
                {'detail': 'JanMitra users cannot access media files.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # All authority roles can preview
        if not user.is_authority:
            return Response(
                {'detail': 'Only authorities can view media previews.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get the media file
        try:
            media = IncidentMedia.objects.select_related('incident').get(
                id=media_id,
                is_deleted=False
            )
        except IncidentMedia.DoesNotExist:
            return Response(
                {'detail': 'Media not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if file exists
        if not media.file:
            raise Http404("File not found")
        
        # Audit log for preview access
        AuditLog.log(
            event_type=AuditEventType.MEDIA_ACCESSED,
            actor=request.user,
            target=media,
            request=request,
            success=True,
            description=f"Media previewed: {media_id}",
            metadata={
                'media_id': str(media_id),
                'incident_id': str(media.incident_id),
                'media_type': media.media_type,
                'access_type': 'preview',
            }
        )
        
        try:
            if media.media_type == 'photo':
                # Generate low-res preview for images
                with media.file.open('rb') as f:
                    img = Image.open(f)
                    
                    # Convert to RGB if necessary (for RGBA, CMYK, etc.)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    
                    # Resize to max 400px on longest side
                    max_size = 400
                    ratio = min(max_size / img.width, max_size / img.height)
                    if ratio < 1:
                        new_size = (int(img.width * ratio), int(img.height * ratio))
                        img = img.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # Save to buffer as JPEG
                    buffer = BytesIO()
                    img.save(buffer, format='JPEG', quality=70)
                    buffer.seek(0)
                    
                    response = FileResponse(
                        buffer,
                        content_type='image/jpeg'
                    )
                    response['Content-Disposition'] = f'inline; filename="preview_{media_id}.jpg"'
                    return response
            
            elif media.media_type == 'video':
                # For videos, try to extract first frame
                # If cv2 is available, use it; otherwise return a placeholder
                try:
                    import cv2
                    import tempfile
                    
                    # Save video to temp file for cv2 to read
                    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                        tmp.write(media.file.read())
                        tmp_path = tmp.name
                    
                    try:
                        cap = cv2.VideoCapture(tmp_path)
                        ret, frame = cap.read()
                        cap.release()
                        
                        if ret:
                            # Resize frame
                            max_size = 400
                            h, w = frame.shape[:2]
                            ratio = min(max_size / w, max_size / h)
                            if ratio < 1:
                                new_size = (int(w * ratio), int(h * ratio))
                                frame = cv2.resize(frame, new_size)
                            
                            # Convert BGR to RGB
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            img = Image.fromarray(frame_rgb)
                            
                            buffer = BytesIO()
                            img.save(buffer, format='JPEG', quality=70)
                            buffer.seek(0)
                            
                            response = FileResponse(
                                buffer,
                                content_type='image/jpeg'
                            )
                            response['Content-Disposition'] = f'inline; filename="preview_{media_id}.jpg"'
                            return response
                    finally:
                        os.unlink(tmp_path)
                
                except ImportError:
                    pass  # cv2 not available
                
                # Fallback: return video file for streaming (first 1MB)
                # This allows the client to show a video preview
                media.file.seek(0)
                chunk = media.file.read(1024 * 1024)  # 1MB chunk
                
                response = FileResponse(
                    BytesIO(chunk),
                    content_type=media.content_type or 'video/mp4'
                )
                response['Content-Disposition'] = f'inline; filename="preview_{media_id}"'
                return response
            
            else:
                return Response(
                    {'detail': 'Preview not available for this media type.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except Exception as e:
            # Log error but don't expose details
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating preview for {media_id}: {e}")
            
            return Response(
                {'detail': 'Failed to generate preview.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )