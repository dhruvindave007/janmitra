"""
Escalation views for JanMitra Backend.

Provides REST API endpoints for:
- Report escalation (Level 2 → Level 1)
- Identity reveal requests and approvals
- Decryption authorization requests

All escalation actions are critical and fully audited.
"""

from django.utils import timezone
from rest_framework import status, generics, views
from rest_framework.response import Response

from .models import (
    Escalation, EscalationStatus,
    IdentityRevealRequest,
    DecryptionRequest,
)
from reports.models import Report
from authentication.models import User, UserRole
from authentication.permissions import (
    IsAuthenticated,
    IsLevel1,
    IsLevel2,
    IsLevel1OrLevel2,
    CanApproveEscalation,
    CanApproveIdentityReveal,
    CanAuthorizeDecryption,
)
from audit.models import AuditLog, AuditEventType


# =============================================================================
# ESCALATION VIEWS
# =============================================================================

class EscalationListView(generics.ListAPIView):
    """
    List escalations.
    
    GET /api/v1/escalation/
    
    - Level 1 sees escalations directed to them or all (if supervisor)
    - Level 2 sees escalations they created
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_level_1:
            # Level 1 sees escalations directed to them
            return Escalation.objects.filter(
                escalated_to=user
            ).order_by('-created_at')
        else:
            # Level 2 sees escalations they created
            return Escalation.objects.filter(
                escalated_by=user
            ).order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        data = []
        for esc in queryset[:50]:
            data.append({
                'id': str(esc.id),
                'report_id': str(esc.report.id),
                'report_number': esc.report.report_number,
                'status': esc.status,
                'priority': esc.priority,
                'reason': esc.reason[:200],
                'escalated_by': esc.escalated_by.identifier,
                'escalated_to': esc.escalated_to.identifier,
                'created_at': esc.created_at.isoformat(),
                'resolved_at': esc.resolved_at.isoformat() if esc.resolved_at else None,
            })
        
        return Response(data)


class EscalationCreateView(views.APIView):
    """
    Create an escalation request.
    
    POST /api/v1/escalation/create/
    
    Request:
    {
        "report_id": "uuid",
        "escalate_to": "uuid",  # Level 1 authority
        "priority": "urgent",
        "reason": "Reason for escalation",
        "additional_notes": "Optional notes"
    }
    
    Only Level 2 can create escalations for reports assigned to them.
    """
    
    permission_classes = [IsLevel2]
    
    def post(self, request):
        report_id = request.data.get('report_id')
        escalate_to_id = request.data.get('escalate_to')
        priority = request.data.get('priority', 'routine')
        reason = request.data.get('reason', '').strip()
        additional_notes = request.data.get('additional_notes', '')
        
        if not report_id:
            return Response(
                {'detail': 'report_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not reason:
            return Response(
                {'detail': 'reason is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get report
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return Response(
                {'detail': 'Report not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if report is assigned to this user
        if report.assigned_to != request.user:
            return Response(
                {'detail': 'You can only escalate reports assigned to you.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get target Level 1 authority
        if escalate_to_id:
            try:
                escalate_to = User.objects.get(
                    id=escalate_to_id,
                    role=UserRole.LEVEL_1,
                    is_active=True
                )
            except User.DoesNotExist:
                return Response(
                    {'detail': 'Invalid Level 1 authority.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Auto-select Level 1 (in production, use proper hierarchy)
            escalate_to = User.objects.filter(
                role=UserRole.LEVEL_1,
                is_active=True
            ).first()
            
            if not escalate_to:
                return Response(
                    {'detail': 'No available Level 1 authority.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Create escalation
        escalation = Escalation.objects.create(
            report=report,
            escalated_by=request.user,
            escalated_to=escalate_to,
            priority=priority,
            reason=reason,
            additional_notes=additional_notes,
            created_by=request.user,
        )
        
        # Update report status
        report.status = 'escalation_pending'
        report.save(update_fields=['status'])
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.ESCALATION_CREATED,
            actor=request.user,
            target=escalation,
            request=request,
            success=True,
            description=f"Escalation created for report {report.report_number}",
            metadata={
                'report_number': report.report_number,
                'priority': priority,
                'escalated_to': str(escalate_to.id)
            }
        )
        
        return Response({
            'id': str(escalation.id),
            'report_number': report.report_number,
            'status': escalation.status,
            'message': 'Escalation request created successfully.'
        }, status=status.HTTP_201_CREATED)


class EscalationDetailView(views.APIView):
    """
    Get escalation details.
    
    GET /api/v1/escalation/{escalation_id}/
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def get(self, request, escalation_id):
        try:
            escalation = Escalation.objects.select_related(
                'report', 'escalated_by', 'escalated_to'
            ).get(id=escalation_id)
        except Escalation.DoesNotExist:
            return Response(
                {'detail': 'Escalation not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Permission check
        user = request.user
        if not (user.is_level_1 or 
                escalation.escalated_by == user or 
                escalation.escalated_to == user):
            return Response(
                {'detail': 'You do not have permission to view this escalation.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return Response({
            'id': str(escalation.id),
            'report': {
                'id': str(escalation.report.id),
                'report_number': escalation.report.report_number,
                'status': escalation.report.status,
                'priority': escalation.report.priority,
            },
            'status': escalation.status,
            'priority': escalation.priority,
            'reason': escalation.reason,
            'additional_notes': escalation.additional_notes,
            'escalated_by': {
                'id': str(escalation.escalated_by.id),
                'identifier': escalation.escalated_by.identifier,
            },
            'escalated_to': {
                'id': str(escalation.escalated_to.id),
                'identifier': escalation.escalated_to.identifier,
            },
            'resolved_at': escalation.resolved_at.isoformat() if escalation.resolved_at else None,
            'resolved_by': escalation.resolved_by.identifier if escalation.resolved_by else None,
            'resolution_notes': escalation.resolution_notes,
            'created_at': escalation.created_at.isoformat(),
        })


class EscalationApproveView(views.APIView):
    """
    Approve an escalation.
    
    POST /api/v1/escalation/{escalation_id}/approve/
    
    Only Level 1 can approve escalations.
    """
    
    permission_classes = [IsLevel1, CanApproveEscalation]
    
    def post(self, request, escalation_id):
        try:
            escalation = Escalation.objects.get(id=escalation_id)
        except Escalation.DoesNotExist:
            return Response(
                {'detail': 'Escalation not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if escalation.status != EscalationStatus.PENDING:
            return Response(
                {'detail': 'Escalation is not pending.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = request.data.get('notes', '')
        
        # Approve escalation
        escalation.approve(request.user, notes)
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.ESCALATION_APPROVED,
            actor=request.user,
            target=escalation,
            request=request,
            success=True,
            description=f"Escalation approved for report {escalation.report.report_number}",
            metadata={
                'report_number': escalation.report.report_number,
            }
        )
        
        return Response({
            'detail': 'Escalation approved.',
            'report_status': escalation.report.status,
        })


class EscalationRejectView(views.APIView):
    """
    Reject an escalation.
    
    POST /api/v1/escalation/{escalation_id}/reject/
    
    Only Level 1 can reject escalations.
    """
    
    permission_classes = [IsLevel1, CanApproveEscalation]
    
    def post(self, request, escalation_id):
        try:
            escalation = Escalation.objects.get(id=escalation_id)
        except Escalation.DoesNotExist:
            return Response(
                {'detail': 'Escalation not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if escalation.status != EscalationStatus.PENDING:
            return Response(
                {'detail': 'Escalation is not pending.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = request.data.get('notes', '')
        if not notes:
            return Response(
                {'detail': 'Rejection notes are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reject escalation
        escalation.reject(request.user, notes)
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.ESCALATION_REJECTED,
            actor=request.user,
            target=escalation,
            request=request,
            success=True,
            description=f"Escalation rejected for report {escalation.report.report_number}",
            metadata={
                'report_number': escalation.report.report_number,
                'rejection_notes': notes[:200],
            }
        )
        
        return Response({'detail': 'Escalation rejected.'})


# =============================================================================
# IDENTITY REVEAL VIEWS
# =============================================================================

class IdentityRevealRequestListView(generics.ListAPIView):
    """
    List identity reveal requests.
    
    GET /api/v1/escalation/identity-reveal/
    
    Only Level 1 can view all identity reveal requests.
    """
    
    permission_classes = [IsLevel1]
    
    def get_queryset(self):
        return IdentityRevealRequest.objects.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        data = []
        for req in queryset[:50]:
            data.append({
                'id': str(req.id),
                'target_user_id': f"JM-{str(req.target_user.id)[:8]}",
                'related_report': req.related_report.report_number if req.related_report else None,
                'requested_by': req.requested_by.identifier,
                'status': req.status,
                'urgency': req.urgency,
                'justification': req.justification[:200],
                'legal_authority': req.legal_authority,
                'created_at': req.created_at.isoformat(),
                'reviewed_at': req.reviewed_at.isoformat() if req.reviewed_at else None,
            })
        
        return Response(data)


class IdentityRevealRequestCreateView(views.APIView):
    """
    Create an identity reveal request.
    
    POST /api/v1/escalation/identity-reveal/create/
    
    Request:
    {
        "target_user_id": "uuid",
        "related_report_id": "uuid",  # optional
        "justification": "Legal and operational justification",
        "legal_authority": "Section XYZ",
        "case_reference": "FIR-123",
        "urgency": "urgent"
    }
    
    Any authority can create a request, but only Level 1 can approve.
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def post(self, request):
        target_user_id = request.data.get('target_user_id')
        related_report_id = request.data.get('related_report_id')
        justification = request.data.get('justification', '').strip()
        legal_authority = request.data.get('legal_authority', '').strip()
        case_reference = request.data.get('case_reference', '')
        urgency = request.data.get('urgency', 'routine')
        
        if not target_user_id:
            return Response(
                {'detail': 'target_user_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not justification:
            return Response(
                {'detail': 'justification is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not legal_authority:
            return Response(
                {'detail': 'legal_authority is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get target JanMitra user
        try:
            target_user = User.objects.get(
                id=target_user_id,
                role=UserRole.LEVEL_3
            )
        except User.DoesNotExist:
            return Response(
                {'detail': 'JanMitra user not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get related report if provided
        related_report = None
        if related_report_id:
            try:
                related_report = Report.objects.get(id=related_report_id)
            except Report.DoesNotExist:
                pass
        
        # Create request
        reveal_request = IdentityRevealRequest.objects.create(
            target_user=target_user,
            related_report=related_report,
            requested_by=request.user,
            justification=justification,
            legal_authority=legal_authority,
            case_reference=case_reference,
            urgency=urgency,
            created_by=request.user,
        )
        
        # Audit log (CRITICAL)
        AuditLog.log(
            event_type=AuditEventType.IDENTITY_REVEAL_REQUESTED,
            actor=request.user,
            target=reveal_request,
            request=request,
            success=True,
            description="Identity reveal requested",
            severity='critical',
            metadata={
                'target_user_id': str(target_user.id),
                'legal_authority': legal_authority,
                'case_reference': case_reference,
            }
        )
        
        return Response({
            'id': str(reveal_request.id),
            'status': reveal_request.status,
            'message': 'Identity reveal request created. Pending Level 1 approval.'
        }, status=status.HTTP_201_CREATED)


class IdentityRevealRequestApproveView(views.APIView):
    """
    Approve an identity reveal request.
    
    POST /api/v1/escalation/identity-reveal/{request_id}/approve/
    
    Only Level 1 can approve.
    """
    
    permission_classes = [IsLevel1, CanApproveIdentityReveal]
    
    def post(self, request, request_id):
        try:
            reveal_request = IdentityRevealRequest.objects.get(id=request_id)
        except IdentityRevealRequest.DoesNotExist:
            return Response(
                {'detail': 'Request not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if reveal_request.status != EscalationStatus.PENDING:
            return Response(
                {'detail': 'Request is not pending.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = request.data.get('notes', '')
        
        # Approve
        reveal_request.approve(request.user, notes)
        
        # Audit log (CRITICAL)
        AuditLog.log(
            event_type=AuditEventType.IDENTITY_REVEAL_APPROVED,
            actor=request.user,
            target=reveal_request,
            request=request,
            success=True,
            description="Identity reveal approved",
            severity='critical',
            metadata={
                'target_user_id': str(reveal_request.target_user.id),
                'approved_by': str(request.user.id),
            }
        )
        
        return Response({
            'detail': 'Identity reveal request approved.',
            'status': reveal_request.status,
        })


class IdentityRevealRequestRejectView(views.APIView):
    """
    Reject an identity reveal request.
    
    POST /api/v1/escalation/identity-reveal/{request_id}/reject/
    """
    
    permission_classes = [IsLevel1, CanApproveIdentityReveal]
    
    def post(self, request, request_id):
        try:
            reveal_request = IdentityRevealRequest.objects.get(id=request_id)
        except IdentityRevealRequest.DoesNotExist:
            return Response(
                {'detail': 'Request not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if reveal_request.status != EscalationStatus.PENDING:
            return Response(
                {'detail': 'Request is not pending.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = request.data.get('notes', '')
        if not notes:
            return Response(
                {'detail': 'Rejection notes are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reject
        reveal_request.reject(request.user, notes)
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.IDENTITY_REVEAL_REJECTED,
            actor=request.user,
            target=reveal_request,
            request=request,
            success=True,
            description="Identity reveal rejected",
            metadata={
                'target_user_id': str(reveal_request.target_user.id),
                'rejection_reason': notes[:200],
            }
        )
        
        return Response({'detail': 'Identity reveal request rejected.'})


class IdentityRevealExecuteView(views.APIView):
    """
    Execute an approved identity reveal.
    
    POST /api/v1/escalation/identity-reveal/{request_id}/execute/
    
    This actually reveals the identity to the requester.
    """
    
    permission_classes = [IsLevel1]
    
    def post(self, request, request_id):
        try:
            reveal_request = IdentityRevealRequest.objects.get(id=request_id)
        except IdentityRevealRequest.DoesNotExist:
            return Response(
                {'detail': 'Request not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if reveal_request.status != EscalationStatus.APPROVED:
            return Response(
                {'detail': 'Request must be approved before execution.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if reveal_request.revealed_at:
            return Response(
                {'detail': 'Identity has already been revealed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute reveal
        reveal_request.execute_reveal(request.user)
        
        # Audit log (CRITICAL)
        AuditLog.log(
            event_type=AuditEventType.IDENTITY_REVEALED,
            actor=request.user,
            target=reveal_request,
            request=request,
            success=True,
            description="Identity revealed",
            severity='critical',
            metadata={
                'target_user_id': str(reveal_request.target_user.id),
                'revealed_to': str(reveal_request.requested_by.id),
            }
        )
        
        # Return revealed identity info
        target_user = reveal_request.target_user
        
        return Response({
            'detail': 'Identity revealed.',
            'identity': {
                'user_id': str(target_user.id),
                'identifier': target_user.identifier,
                'created_at': target_user.created_at.isoformat(),
            }
        })


# =============================================================================
# DECRYPTION REQUEST VIEWS
# =============================================================================

class DecryptionRequestListView(generics.ListAPIView):
    """
    List decryption requests.
    
    GET /api/v1/escalation/decryption/
    """
    
    permission_classes = [IsLevel1]
    
    def list(self, request, *args, **kwargs):
        queryset = DecryptionRequest.objects.order_by('-created_at')
        
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        data = []
        for req in queryset[:50]:
            data.append({
                'id': str(req.id),
                'report_id': str(req.report.id),
                'report_number': req.report.report_number,
                'requested_by': req.requested_by.identifier,
                'status': req.status,
                'reason': req.reason[:200],
                'include_media': req.include_media,
                'created_at': req.created_at.isoformat(),
                'reviewed_at': req.reviewed_at.isoformat() if req.reviewed_at else None,
            })
        
        return Response(data)


class DecryptionRequestCreateView(views.APIView):
    """
    Create a decryption request.
    
    POST /api/v1/escalation/decryption/create/
    """
    
    permission_classes = [IsLevel1OrLevel2]
    
    def post(self, request):
        report_id = request.data.get('report_id')
        reason = request.data.get('reason', '').strip()
        legal_authority = request.data.get('legal_authority', '')
        case_reference = request.data.get('case_reference', '')
        include_media = request.data.get('include_media', False)
        
        if not report_id:
            return Response(
                {'detail': 'report_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not reason:
            return Response(
                {'detail': 'reason is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return Response(
                {'detail': 'Report not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already authorized
        if report.decryption_authorized:
            return Response(
                {'detail': 'Decryption is already authorized for this report.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create request
        decrypt_request = DecryptionRequest.objects.create(
            report=report,
            requested_by=request.user,
            reason=reason,
            legal_authority=legal_authority,
            case_reference=case_reference,
            include_media=include_media,
            created_by=request.user,
        )
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.DECRYPTION_REQUESTED,
            actor=request.user,
            target=decrypt_request,
            request=request,
            success=True,
            description=f"Decryption requested for report {report.report_number}",
            metadata={
                'report_number': report.report_number,
                'include_media': include_media,
            }
        )
        
        return Response({
            'id': str(decrypt_request.id),
            'status': decrypt_request.status,
            'message': 'Decryption request created. Pending Level 1 approval.'
        }, status=status.HTTP_201_CREATED)


class DecryptionRequestApproveView(views.APIView):
    """
    Approve a decryption request.
    
    POST /api/v1/escalation/decryption/{request_id}/approve/
    """
    
    permission_classes = [IsLevel1, CanAuthorizeDecryption]
    
    def post(self, request, request_id):
        try:
            decrypt_request = DecryptionRequest.objects.get(id=request_id)
        except DecryptionRequest.DoesNotExist:
            return Response(
                {'detail': 'Request not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if decrypt_request.status != EscalationStatus.PENDING:
            return Response(
                {'detail': 'Request is not pending.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = request.data.get('notes', '')
        
        # Approve
        decrypt_request.approve(request.user, notes)
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.DECRYPTION_APPROVED,
            actor=request.user,
            target=decrypt_request,
            request=request,
            success=True,
            description=f"Decryption approved for report {decrypt_request.report.report_number}",
            metadata={
                'report_number': decrypt_request.report.report_number,
            }
        )
        
        return Response({
            'detail': 'Decryption request approved.',
            'report_decryption_authorized': True,
        })


class DecryptionRequestRejectView(views.APIView):
    """
    Reject a decryption request.
    
    POST /api/v1/escalation/decryption/{request_id}/reject/
    """
    
    permission_classes = [IsLevel1, CanAuthorizeDecryption]
    
    def post(self, request, request_id):
        try:
            decrypt_request = DecryptionRequest.objects.get(id=request_id)
        except DecryptionRequest.DoesNotExist:
            return Response(
                {'detail': 'Request not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if decrypt_request.status != EscalationStatus.PENDING:
            return Response(
                {'detail': 'Request is not pending.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = request.data.get('notes', '')
        if not notes:
            return Response(
                {'detail': 'Rejection notes are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reject
        decrypt_request.reject(request.user, notes)
        
        # Audit log
        AuditLog.log(
            event_type=AuditEventType.DECRYPTION_REJECTED,
            actor=request.user,
            target=decrypt_request,
            request=request,
            success=True,
            description=f"Decryption rejected for report {decrypt_request.report.report_number}",
            metadata={
                'report_number': decrypt_request.report.report_number,
                'rejection_reason': notes[:200],
            }
        )
        
        return Response({'detail': 'Decryption request rejected.'})
