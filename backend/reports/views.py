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
from .services import BroadcastIncidentService, IncidentCreationError


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
    Create incident from citizen submission.
    
    POST /api/v1/incidents/broadcast/
    
    Request (multipart/form-data or JSON):
    {
        "description": "Incident description",
        "incident_location": "SG Highway near Iscon Mall",
        "category": "THEFT",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "media_files": [file1, file2, file3]  (optional, max 3)
    }
    
    Response:
    {
        "incident_id": "uuid",
        "case_id": "uuid",
        "media_uploaded": 2,
        "message": "Incident reported successfully"
    }
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def post(self, request):
        # Accept both "description" and "text_content" for flexibility
        description = request.data.get('description') or request.data.get('text_content', '')
        description = description.strip() if description else ''
        
        if not description:
            return Response(
                {'error': 'description is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # V2: incident_location is REQUIRED
        incident_location = request.data.get('incident_location', '')
        incident_location = incident_location.strip() if incident_location else ''
        if not incident_location:
            return Response(
                {'error': 'Please enter a valid incident location'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # V2: GPS is MANDATORY
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        if latitude is None or longitude is None:
            return Response(
                {'error': 'GPS location is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # V2: Category is REQUIRED
        category = request.data.get('category', '')
        if not category or category not in IncidentCategory.VALID_VALUES:
            return Response(
                {'error': 'Please select a valid incident category'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            incident, case, media_uploaded, media_errors = BroadcastIncidentService.execute(
                user=request.user,
                text_content=description,
                incident_location=incident_location,
                category=category,
                latitude=latitude,
                longitude=longitude,
                media_files=request.FILES.getlist('media_files') or request.FILES.getlist('media'),
                area_name=request.data.get('area_name'),
                city=request.data.get('city'),
                state=request.data.get('state'),
            )
        except IncidentCreationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Audit log (non-blocking)
        try:
            AuditLog.log(
                event_type=AuditEventType.REPORT_CREATED,
                actor=request.user,
                target=incident,
                request=request,
                success=True,
                description=f"Incident created: {incident.id}",
                metadata={
                    'incident_id': str(incident.id),
                    'case_id': str(case.id),
                    'police_station': str(case.police_station_id) if case.police_station else None,
                }
            )
        except Exception:
            pass
        
        # Clean minimal response
        response_data = {
            'incident_id': str(incident.id),
            'case_id': str(case.id),
            'media_uploaded': media_uploaded,
            'message': 'Incident reported successfully',
        }
        if case.police_station:
            response_data['police_station'] = case.police_station.name
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
    L0/L1/L2 can mark cases as solved. This does NOT close the case.
    L2 must then close the case after reviewing.
    
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
        
        # Allow solving from any non-terminal status
        terminal = {CaseStatus.SOLVED, CaseStatus.CLOSED, CaseStatus.REJECTED, CaseStatus.RESOLVED}
        if case.status in terminal:
            return Response(
                {'detail': f'Case is already {case.status}. Cannot solve.'},
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
        
        # Notify L2 at same station that case needs closure
        try:
            NotificationService.notify_case_solved_new(case, request.user)
        except Exception:
            pass  # Non-critical
        
        return Response({'detail': 'Case marked as solved.'})


class CloseCaseView(views.APIView):
    """
    Close a solved case. Only L2 (PI) can close cases.
    
    POST /api/v1/incidents/{case_id}/close/
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
        
        # Only L2+ can close cases
        user = request.user
        if not (user.is_level_2 or user.is_level_2_captain or 
                getattr(user, 'role', None) in ['L2', 'L3', 'L4']):
            return Response(
                {'detail': 'Only L2 or higher can close cases.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Can only close solved cases
        if case.status != CaseStatus.SOLVED:
            return Response(
                {'detail': f'Case must be solved before closing. Current status: {case.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        closure_notes = request.data.get('closure_notes', '')
        
        old_status = case.status
        case.status = CaseStatus.CLOSED
        case.closed_at = timezone.now()
        case.closed_by = request.user
        case.save()
        
        # Status history
        CaseStatusHistory.objects.create(
            case=case,
            from_status=old_status,
            to_status=CaseStatus.CLOSED,
            changed_by=request.user,
            reason=closure_notes or 'Case closed after review'
        )
        
        # Notify assigned officer
        try:
            NotificationService.notify_case_closed_new(case, request.user)
        except Exception:
            pass  # Non-critical
        
        return Response({'detail': 'Case closed successfully.'})


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
        
        # Allow forwarding from any non-terminal status
        terminal = {CaseStatus.SOLVED, CaseStatus.CLOSED, CaseStatus.REJECTED, CaseStatus.RESOLVED}
        if case.status in terminal:
            return Response(
                {'detail': f'Case is already {case.status}. Cannot forward.'},
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
        
        # Allow rejection from any non-terminal status
        terminal = {CaseStatus.SOLVED, CaseStatus.CLOSED, CaseStatus.REJECTED, CaseStatus.RESOLVED}
        if case.status in terminal:
            return Response(
                {'detail': f'Case is already {case.status}. Cannot reject.'},
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
    List cases for all roles based on visibility rules.
    
    GET /api/v1/incidents/cases/
    
    Visibility rules:
    - L0: Only cases assigned to them
    - L1/L2: All cases at their police station
    - L3: Cases escalated to L3 or L4 level
    - L4: Cases at L4 level
    - JANMITRA: No access (403 Forbidden)
    
    Query parameters:
    - status: Filter by status (new, assigned, in_progress, escalated, resolved, closed)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = CaseListSerializer
    
    def get_queryset(self):
        from .models import visible_cases_for_user
        from authentication.models import UserRole
        
        user = self.request.user
        
        # JANMITRA has no access
        if getattr(user, 'role', None) == UserRole.JANMITRA:
            return Case.objects.none()
        
        queryset = visible_cases_for_user(user)
        
        # Optional status filter
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
        ).exclude(
            status__in=[CaseStatus.SOLVED, CaseStatus.CLOSED, CaseStatus.REJECTED, CaseStatus.RESOLVED]
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
    Returns 403 PermissionDenied if user cannot access the case.
    Returns 404 if case does not exist.
    """
    
    permission_classes = [IsAuthenticated]

    def get(self, request, case_id):
        from .models import visible_cases_for_user
        from authentication.models import UserRole
        from rest_framework.exceptions import PermissionDenied
        
        user = request.user
        
        # JANMITRA has no access to case details
        if getattr(user, 'role', None) == UserRole.JANMITRA:
            raise PermissionDenied("JanMitra users cannot access case details")
        
        # Check if case exists first
        try:
            case = Case.objects.select_related(
                'incident', 'incident__submitted_by', 
                'police_station', 'assigned_officer', 'assigned_by'
            ).prefetch_related(
                'incident__media_files', 'notes', 'notes__author'
            ).get(id=case_id, is_deleted=False)
        except Case.DoesNotExist:
            return Response(
                {'error': 'Case not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user has access via visible_cases_for_user
        visible_ids = visible_cases_for_user(user).values_list('id', flat=True)
        if case.id not in visible_ids:
            raise PermissionDenied("You do not have access to this case")
        
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
        
        serializer = IncidentMediaSerializer(media_files, many=True, context={'request': request})
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


# =============================================================================
# ASSIGNMENT VIEWS (L1 assigns L0 to cases)
# =============================================================================

from .services import (
    AssignmentService,
    AssignmentError,
    InvalidOfficerError,
    InvalidAssignerError,
    CaseNotAssignableError,
)
from authentication.models import User


class AssignCaseView(views.APIView):
    """
    Assign an L0 officer to a case. Overwrites existing assignment.
    
    POST /api/v1/incidents/cases/<case_id>/assign/
    
    Request:
    {
        "officer_id": "uuid",
        "notes": "optional"
    }
    
    Response:
    {
        "case_id": "uuid",
        "officer_id": "uuid",
        "assigned_at": "iso_timestamp"
    }
    
    Rules:
    - Only L1 can assign
    - Officer must be L0 at same station
    - Overwrites existing assignment (only one L0 per case)
    """
    
    permission_classes = [IsLevel1]
    
    def post(self, request, case_id):
        try:
            case = Case.objects.get(id=case_id, is_deleted=False)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)
        
        officer_id = request.data.get('officer_id')
        if not officer_id:
            return Response({'error': 'officer_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            officer = User.objects.get(id=officer_id, is_deleted=False)
        except User.DoesNotExist:
            return Response({'error': 'Officer not found'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            updated_case = AssignmentService.assign_officer(
                case=case,
                officer=officer,
                assigned_by=request.user,
                notes=request.data.get('notes', '')
            )
        except InvalidOfficerError as e:
            return Response({'error': str(e), 'code': 'invalid_officer'}, status=status.HTTP_400_BAD_REQUEST)
        except InvalidAssignerError as e:
            return Response({'error': str(e), 'code': 'invalid_assigner'}, status=status.HTTP_403_FORBIDDEN)
        except CaseNotAssignableError as e:
            return Response({'error': str(e), 'code': 'case_not_assignable'}, status=status.HTTP_400_BAD_REQUEST)
        except AssignmentError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            AuditLog.log(
                event_type=AuditEventType.CASE_ASSIGNED,
                actor=request.user,
                target=updated_case,
                request=request,
                success=True,
                description=f"Case {case_id} assigned to {officer.identifier}",
                metadata={'case_id': str(case_id), 'officer_id': str(officer_id)}
            )
        except Exception:
            pass
        
        return Response({
            'case_id': str(updated_case.id),
            'officer_id': str(officer.id),
            'officer_identifier': officer.identifier,
            'assigned_at': updated_case.assigned_at.isoformat() if updated_case.assigned_at else None,
        })


class AvailableOfficersView(views.APIView):
    """
    List L0 officers available for assignment.
    
    GET /api/v1/incidents/cases/<case_id>/officers/
    """
    
    permission_classes = [IsLevel1]
    
    def get(self, request, case_id):
        try:
            case = Case.objects.get(id=case_id, is_deleted=False)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user.police_station != case.police_station:
            return Response({'error': 'Not your station'}, status=status.HTTP_403_FORBIDDEN)
        
        officers = AssignmentService.get_available_officers(case)
        
        return Response({
            'officers': [
                {
                    'id': str(o.id),
                    'identifier': o.identifier,
                    'workload': AssignmentService.get_officer_workload(o),
                }
                for o in officers
            ]
        })


# =============================================================================
# INVESTIGATION CHAT VIEWS
# =============================================================================

class InvestigationMessagesView(views.APIView):
    """
    Get investigation chat messages for a case.
    
    GET /api/v1/incidents/cases/<case_id>/messages/
    Query params:
    - limit: max messages to return (default 50)
    - before_id: get messages before this ID (pagination)
    - after_id: get messages after this ID (new messages)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, case_id):
        try:
            case = Case.objects.get(id=case_id, is_deleted=False)
        except Case.DoesNotExist:
            return Response(
                {'error': 'Case not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        from .services import InvestigationService, AccessDeniedError
        
        try:
            # Get query params
            limit = int(request.query_params.get('limit', 50))
            limit = min(max(limit, 1), 100)  # Clamp between 1 and 100
            before_id = request.query_params.get('before_id')
            after_id = request.query_params.get('after_id')
            
            messages = InvestigationService.get_messages(
                case=case,
                user=request.user,
                limit=limit,
                before_id=before_id,
                after_id=after_id
            )
            
            return Response({
                'messages': [
                    {
                        'id': str(m.id),
                        'sender_id': str(m.sender.id) if m.sender else None,
                        'sender_identifier': m.sender.identifier if m.sender else 'SYSTEM',
                        'sender_role': m.sender_role,
                        'message_type': m.message_type,
                        'text_content': m.text_content,
                        'file_name': m.file_name,
                        'file_size': m.file_size,
                        'file_type': m.file_type,
                        'has_media': bool(m.file),
                        'created_at': m.created_at.isoformat(),
                    }
                    for m in messages
                ],
                'count': len(messages),
                'case_id': str(case_id),
                'is_chat_locked': case.is_chat_locked,
            })
            
        except AccessDeniedError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )


class SendMessageView(views.APIView):
    """
    Send a text message to case investigation chat.
    
    POST /api/v1/incidents/cases/<case_id>/messages/
    {
        "text": "message content"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, case_id):
        try:
            case = Case.objects.get(id=case_id, is_deleted=False)
        except Case.DoesNotExist:
            return Response(
                {'error': 'Case not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        text = request.data.get('text', '').strip()
        if not text:
            return Response(
                {'error': 'Message text is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from .services import (
            InvestigationService, 
            AccessDeniedError, 
            ChatLockedError,
            InvalidMessageError
        )
        
        try:
            message = InvestigationService.send_message(
                case=case,
                sender=request.user,
                text=text
            )
            
            return Response({
                'message': {
                    'id': str(message.id),
                    'sender_id': str(message.sender.id),
                    'sender_identifier': message.sender.identifier,
                    'sender_role': message.sender_role,
                    'message_type': message.message_type,
                    'text_content': message.text_content,
                    'created_at': message.created_at.isoformat(),
                }
            }, status=status.HTTP_201_CREATED)
            
        except AccessDeniedError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ChatLockedError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except InvalidMessageError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class SendMediaMessageView(views.APIView):
    """
    Send a media message to case investigation chat.
    
    POST /api/v1/incidents/cases/<case_id>/messages/media/
    Content-Type: multipart/form-data
    - file: media file
    - caption: optional text caption
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, case_id):
        try:
            case = Case.objects.get(id=case_id, is_deleted=False)
        except Case.DoesNotExist:
            return Response(
                {'error': 'Case not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': 'File is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        caption = request.data.get('caption', '')
        
        from .services import (
            InvestigationService,
            AccessDeniedError,
            ChatLockedError,
            InvalidMessageError
        )
        
        try:
            message = InvestigationService.send_media_message(
                case=case,
                sender=request.user,
                file=file,
                file_name=file.name,
                caption=caption
            )
            
            return Response({
                'message': {
                    'id': str(message.id),
                    'sender_id': str(message.sender.id),
                    'sender_identifier': message.sender.identifier,
                    'sender_role': message.sender_role,
                    'message_type': message.message_type,
                    'text_content': message.text_content,
                    'file_name': message.file_name,
                    'file_size': message.file_size,
                    'file_type': message.file_type,
                    'has_media': bool(message.file),
                    'created_at': message.created_at.isoformat(),
                }
            }, status=status.HTTP_201_CREATED)
            
        except AccessDeniedError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ChatLockedError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except InvalidMessageError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class MessageMediaDownloadView(views.APIView):
    """
    Download media attachment from an investigation message.
    
    GET /api/v1/incidents/messages/<message_id>/download/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, message_id):
        from .models import InvestigationMessage
        from django.http import FileResponse, Http404
        
        try:
            message = InvestigationMessage.objects.select_related('case').get(
                id=message_id, 
                is_deleted=False
            )
        except InvestigationMessage.DoesNotExist:
            return Response(
                {'error': 'Message not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not message.file:
            return Response(
                {'error': 'Message has no media attachment'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        from .services import InvestigationService, AccessDeniedError
        
        # Check access to the case
        try:
            InvestigationService._validate_access(message.case, request.user)
        except AccessDeniedError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Return file
        try:
            response = FileResponse(
                message.file.open('rb'),
                content_type=message.file_type or 'application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{message.file_name or "file"}"'
            return response
        except FileNotFoundError:
            return Response(
                {'error': 'File not found on server'},
                status=status.HTTP_404_NOT_FOUND
            )


class DeleteMessageView(views.APIView):
    """
    Delete an investigation message (soft delete).
    Only the author can delete their own message.
    
    DELETE /api/v1/incidents/messages/<message_id>/delete/
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, message_id):
        from .models import InvestigationMessage
        from .services import InvestigationService, AccessDeniedError
        
        try:
            message = InvestigationMessage.objects.select_related('case').get(
                id=message_id,
                is_deleted=False
            )
        except InvestigationMessage.DoesNotExist:
            return Response(
                {'error': 'Message not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            InvestigationService.delete_message(message, request.user)
            return Response(
                {'message': 'Message deleted successfully'},
                status=status.HTTP_200_OK
            )
        except AccessDeniedError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except PermissionError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )