"""
Admin configuration for reports models.

PHASE 4.1: Admin Control Center

Design principles:
- READ-ONLY for Incidents (immutable submissions)
- READ-ONLY for Cases (but with admin ACTIONS for force operations)
- Full audit logging for all admin actions
- Fieldsets for clarity
- Prevent accidental modifications
"""

from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from django.utils.html import format_html
from datetime import timedelta

from .models import (
    Report, ReportStatusHistory, ReportNote,
    Incident, Case, CaseNote, CaseStatusHistory, CaseStatus, CaseLevel,
    IncidentMedia, InvestigationMessage, EscalationHistory,
)
from audit.models import AuditLog, AuditEventType
from notifications.services import NotificationService


# =============================================================================
# INCIDENT ADMIN (READ-ONLY)
# =============================================================================

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    """
    Admin for Incident model.
    
    STRICTLY READ-ONLY: Incidents are immutable citizen submissions.
    No add/edit/delete operations allowed.
    """
    
    list_display = [
        'short_id', 
        'category', 
        'short_text', 
        'submitted_by_display',
        'area_name',
        'has_location',
        'created_at',
    ]
    list_filter = ['category', 'created_at']
    search_fields = ['id', 'text_content', 'submitted_by__identifier', 'area_name', 'city', 'state']
    ordering = ['-created_at']
    list_select_related = ['submitted_by']
    
    # ALL fields read-only
    readonly_fields = [
        'id', 'submitted_by', 'text_content', 'category',
        'latitude', 'longitude', 'area_name', 'city', 'state',
        'created_at', 'updated_at',
        'has_location_display', 'case_link',
    ]
    
    fieldsets = (
        ('Identification', {
            'fields': ('id', 'case_link'),
        }),
        ('Submitter', {
            'fields': ('submitted_by',),
        }),
        ('Content', {
            'fields': ('category', 'text_content'),
        }),
        ('Location', {
            'fields': ('has_location_display', 'latitude', 'longitude'),
        }),
        ('Area Metadata', {
            'fields': ('area_name', 'city', 'state'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    # === Display helpers ===
    
    def short_id(self, obj):
        """Display shortened UUID."""
        return str(obj.id)[:8] + '...'
    short_id.short_description = 'ID'
    short_id.admin_order_field = 'id'
    
    def short_text(self, obj):
        """Truncate incident text for list view."""
        text = obj.text_content or ''
        return text[:50] + '...' if len(text) > 50 else text
    short_text.short_description = 'Incident Text'
    
    def submitted_by_display(self, obj):
        """Display submitter identifier."""
        if obj.submitted_by:
            return obj.submitted_by.identifier
        return '-'
    submitted_by_display.short_description = 'Submitted By'
    submitted_by_display.admin_order_field = 'submitted_by__identifier'
    
    def has_location_display(self, obj):
        """Display location availability as icon."""
        return obj.has_location
    has_location_display.boolean = True
    has_location_display.short_description = 'Has Location'
    
    def case_link(self, obj):
        """Link to associated case if exists."""
        if hasattr(obj, 'case') and obj.case:
            from django.urls import reverse
            url = reverse('admin:reports_case_change', args=[obj.case.id])
            return format_html('<a href="{}">Case: {}</a>', url, str(obj.case.id)[:8])
        return 'No case created'
    case_link.short_description = 'Associated Case'
    
    # === Permissions (READ-ONLY) ===
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        # Allow viewing but not editing
        return True
    
    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================================
# CASE ADMIN INLINES
# =============================================================================

class RecentMessagesInline(admin.TabularInline):
    """Read-only inline showing last 5 investigation messages on a case."""
    model = InvestigationMessage
    fields = ['sender', 'sender_role', 'message_type', 'short_text_display', 'created_at']
    readonly_fields = ['sender', 'sender_role', 'message_type', 'short_text_display', 'created_at']
    extra = 0
    max_num = 0
    verbose_name = 'Recent Message'
    verbose_name_plural = '💬 Recent Investigation Messages (last 5)'
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            is_deleted=False
        ).select_related('sender').order_by('-created_at')[:5]

    def short_text_display(self, obj):
        text = obj.text_content or ''
        return text[:80] + '…' if len(text) > 80 else text or '-'
    short_text_display.short_description = 'Content'


class CaseEscalationInline(admin.TabularInline):
    """Read-only inline showing escalation history for a case."""
    model = EscalationHistory
    fields = ['event_type', 'level_display', 'escalation_type', 'escalated_by', 'reason_short', 'created_at']
    readonly_fields = ['event_type', 'level_display', 'escalation_type', 'escalated_by', 'reason_short', 'created_at']
    extra = 0
    max_num = 0
    verbose_name = 'Escalation'
    verbose_name_plural = '🔺 Escalation History'
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            is_deleted=False
        ).select_related('escalated_by', 'assigned_officer').order_by('-created_at')

    def level_display(self, obj):
        from_l = obj.from_level or '—'
        to_l = obj.to_level or '—'
        return f'{from_l} → {to_l}'
    level_display.short_description = 'Level Change'

    def reason_short(self, obj):
        text = obj.reason or ''
        return text[:60] + '…' if len(text) > 60 else text or '-'
    reason_short.short_description = 'Reason'


# =============================================================================
# CASE ADMIN (READ-ONLY + ADMIN ACTIONS)
# =============================================================================

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    """
    Admin for Case model.
    
    READ-ONLY for all fields, but with ADMIN ACTIONS for:
    - Force escalation
    - Force close
    
    All actions are fully audited.
    """
    
    list_display = [
        'case_number',
        'incident_preview',
        'station_name',
        'status_badge',
        'level_badge',
        'assigned_officer_display',
        'sla_indicator',
        'escalation_count',
        'created_at',
    ]
    list_filter = ['status', 'current_level', 'police_station', 'created_at']
    search_fields = ['id', 'incident__id', 'incident__text_content', 'police_station__name', 'assigned_officer__identifier']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30
    list_select_related = ['incident', 'police_station', 'assigned_officer']
    inlines = [RecentMessagesInline, CaseEscalationInline]
    
    # ALL fields read-only
    readonly_fields = [
        'id', 'incident', 'incident_link', 'incident_text_display',
        'police_station', 'assigned_officer', 'assigned_by',
        'status', 'current_level', 
        'sla_deadline', 'is_sla_breached_display',
        'escalation_count', 'last_escalated_at',
        'solved_at', 'solved_by', 'solution_notes',
        'rejected_at', 'rejected_by', 'rejection_reason',
        'created_at', 'updated_at',
    ]
    
    fieldsets = (
        ('Case Identification', {
            'fields': ('id', 'incident_link', 'incident_text_display'),
        }),
        ('Assignment', {
            'fields': ('police_station', 'assigned_officer', 'assigned_by'),
        }),
        ('Current Status', {
            'fields': ('status', 'current_level'),
        }),
        ('SLA Tracking', {
            'fields': ('sla_deadline', 'is_sla_breached_display', 'escalation_count', 'last_escalated_at'),
        }),
        ('Resolution', {
            'fields': ('solved_at', 'solved_by', 'solution_notes'),
            'classes': ('collapse',),
        }),
        ('Rejection', {
            'fields': ('rejected_at', 'rejected_by', 'rejection_reason'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    # Admin actions
    actions = ['force_escalate_case', 'force_close_case']
    
    # === Display helpers ===
    
    def case_number(self, obj):
        """Show case ID as compact reference number."""
        return f'#{str(obj.id)[:8]}'
    case_number.short_description = 'Case #'
    case_number.admin_order_field = 'id'
    
    def incident_preview(self, obj):
        """Show truncated incident text."""
        if obj.incident:
            text = obj.incident.text_content or ''
            return text[:40] + '...' if len(text) > 40 else text
        return '-'
    incident_preview.short_description = 'Incident'
    
    def status_badge(self, obj):
        """Color-coded status badge with all case statuses."""
        colors = {
            'new': '#3498db',          # Blue
            'assigned': '#2980b9',     # Dark Blue
            'in_progress': '#f39c12',  # Yellow
            'escalated': '#e67e22',    # Orange
            'solved': '#27ae60',       # Green
            'rejected': '#e74c3c',     # Red
            'closed': '#7f8c8d',       # Gray
            'resolved': '#2ecc71',     # Light Green
        }
        color = colors.get(obj.status, '#95a5a6')
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; '
            'border-radius:3px; font-size:11px; font-weight:600;">{}</span>',
            color, obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def level_badge(self, obj):
        """Color-coded level badge."""
        colors = {
            CaseLevel.LEVEL_2: '#9b59b6',  # Purple
            CaseLevel.LEVEL_1: '#e67e22',  # Orange
            CaseLevel.LEVEL_0: '#c0392b',  # Dark Red
        }
        color = colors.get(obj.current_level, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">L{}</span>',
            color, obj.current_level
        )
    level_badge.short_description = 'Level'
    level_badge.admin_order_field = 'current_level'
    
    def sla_indicator(self, obj):
        """Compact SLA status: time remaining or breach indicator."""
        terminal = {'solved', 'closed', 'rejected', 'resolved'}
        if obj.status in terminal:
            return format_html('<span style="color:#7f8c8d;">—</span>')
        
        now = timezone.now()
        if now > obj.sla_deadline:
            hours_over = (now - obj.sla_deadline).total_seconds() / 3600
            return format_html(
                '<span style="background:#e74c3c; color:#fff; padding:2px 6px; '
                'border-radius:3px; font-size:11px;">⚠ +{:.0f}h</span>', hours_over
            )
        
        hours_left = (obj.sla_deadline - now).total_seconds() / 3600
        if hours_left < 6:
            color = '#e67e22'  # Orange — nearing
        else:
            color = '#27ae60'  # Green — OK
        return format_html(
            '<span style="color:{}; font-weight:600; font-size:11px;">{:.0f}h left</span>',
            color, hours_left
        )
    sla_indicator.short_description = 'SLA'
    
    def is_sla_breached_display(self, obj):
        """Display SLA breach status in detail view."""
        terminal = {'solved', 'closed', 'rejected', 'resolved'}
        return timezone.now() > obj.sla_deadline and obj.status not in terminal
    is_sla_breached_display.boolean = True
    is_sla_breached_display.short_description = 'SLA Breached?'
    
    def incident_link(self, obj):
        """Link to incident."""
        if obj.incident:
            from django.urls import reverse
            url = reverse('admin:reports_incident_change', args=[obj.incident.id])
            return format_html('<a href="{}">Incident: {}</a>', url, str(obj.incident.id)[:8])
        return '-'
    incident_link.short_description = 'Source Incident'
    
    def incident_text_display(self, obj):
        """Display full incident text."""
        if obj.incident:
            return obj.incident.text_content
        return '-'
    incident_text_display.short_description = 'Incident Text'
    
    def station_name(self, obj):
        """Display police station name."""
        return obj.police_station.name if obj.police_station else '-'
    station_name.short_description = 'Station'
    station_name.admin_order_field = 'police_station__name'
    
    def assigned_officer_display(self, obj):
        """Display assigned officer identifier."""
        return obj.assigned_officer.identifier if obj.assigned_officer else '-'
    assigned_officer_display.short_description = 'Officer'
    assigned_officer_display.admin_order_field = 'assigned_officer__identifier'
    
    # === Admin Actions ===
    
    @admin.action(description="🔺 Force Escalate to Next Level")
    def force_escalate_case(self, request, queryset):
        """
        Force escalate selected cases to the next higher level.
        current_level is monotonic — only increases (L1→L2→L3→L4).
        """
        LEVEL_ORDER = ['L0', 'L1', 'L2', 'L3', 'L4']
        terminal = {'solved', 'closed', 'rejected', 'resolved'}
        escalated_count = 0
        skipped_count = 0
        
        for case in queryset:
            if case.status in terminal:
                skipped_count += 1
                continue
            
            try:
                idx = LEVEL_ORDER.index(case.current_level)
            except ValueError:
                skipped_count += 1
                continue
            
            if idx >= len(LEVEL_ORDER) - 1:  # Already L4
                skipped_count += 1
                continue
            
            prev_level = case.current_level
            prev_status = case.status
            
            # Escalate — monotonic increase
            case.current_level = LEVEL_ORDER[idx + 1]
            case.status = CaseStatus.ESCALATED
            case.escalation_count += 1
            case.last_escalated_at = timezone.now()
            case.sla_deadline = timezone.now() + timedelta(hours=48)
            case.save()
            
            # Create status history
            CaseStatusHistory.objects.create(
                case=case,
                from_status=prev_status,
                to_status=case.status,
                from_level=prev_level,
                to_level=case.current_level,
                changed_by=request.user,
                reason=f"Admin force escalation by {request.user.identifier}",
                is_auto_escalation=False,
            )
            
            # Audit log
            AuditLog.log(
                event_type=AuditEventType.ESCALATION_CREATED,
                actor=request.user,
                target=case,
                request=request,
                success=True,
                description=f"Admin force escalated case from Level {prev_level} to Level {case.current_level}",
                metadata={
                    'case_id': str(case.id),
                    'from_level': prev_level,
                    'to_level': case.current_level,
                    'action': 'force_escalate',
                    'admin_user': request.user.identifier,
                }
            )
            
            # Notify authorities about admin force escalation
            try:
                NotificationService.notify_admin_force_escalation(
                    case=case,
                    from_level=prev_level,
                    to_level=case.current_level,
                    admin_user=request.user,
                    reason=f"Admin force escalation by {request.user.identifier}"
                )
            except Exception:
                pass  # Non-critical
            
            escalated_count += 1
        
        if escalated_count > 0:
            self.message_user(
                request,
                f"Successfully escalated {escalated_count} case(s). SLA reset to 24h.",
                messages.SUCCESS
            )
        if skipped_count > 0:
            self.message_user(
                request,
                f"Skipped {skipped_count} case(s) (terminal state or already at L4).",
                messages.WARNING
            )
    
    @admin.action(description="🔒 Force Close Case")
    def force_close_case(self, request, queryset):
        """
        Force close selected cases.
        
        - Sets status to CLOSED
        - Records admin as closer
        - Creates CaseStatusHistory
        - Logs to AuditLog
        """
        closed_count = 0
        skipped_count = 0
        
        for case in queryset:
            # Skip if already terminal
            terminal = {'solved', 'closed', 'rejected', 'resolved'}
            if case.status in terminal:
                skipped_count += 1
                continue
            
            # Store previous state for audit
            prev_status = case.status
            prev_level = case.current_level
            
            # Close the case
            case.status = CaseStatus.CLOSED
            case.save()
            
            # Create status history
            CaseStatusHistory.objects.create(
                case=case,
                from_status=prev_status,
                to_status=CaseStatus.CLOSED,
                from_level=prev_level,
                to_level=prev_level,
                changed_by=request.user,
                reason=f"Admin force closed by {request.user.identifier}",
                is_auto_escalation=False,
            )
            
            # Audit log
            AuditLog.log(
                event_type=AuditEventType.REPORT_STATUS_CHANGED,
                actor=request.user,
                target=case,
                request=request,
                success=True,
                description=f"Admin force closed case (was: {prev_status})",
                metadata={
                    'case_id': str(case.id),
                    'from_status': prev_status,
                    'to_status': CaseStatus.CLOSED,
                    'action': 'force_close',
                    'admin_user': request.user.identifier,
                }
            )
            
            # Notify authorities about the admin force close
            try:
                NotificationService.notify_case_closed(
                    case=case,
                    closed_by=request.user,
                    reason=f"Admin force closed by {request.user.identifier}"
                )
            except Exception:
                pass  # Non-critical
            
            closed_count += 1
        
        if closed_count > 0:
            self.message_user(
                request,
                f"Successfully closed {closed_count} case(s).",
                messages.SUCCESS
            )
        if skipped_count > 0:
            self.message_user(
                request,
                f"Skipped {skipped_count} case(s) (already in terminal state).",
                messages.WARNING
            )
    
    # === Queryset optimization ===
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'incident', 'police_station', 'assigned_officer', 'assigned_by',
            'solved_by', 'rejected_by',
        ).prefetch_related(
            'status_history', 'escalation_history',
        )
    
    # === Permissions ===
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        # Allow viewing but not field editing
        return True
    
    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================================
# CASE NOTE ADMIN (READ-ONLY)
# =============================================================================

@admin.register(CaseNote)
class CaseNoteAdmin(admin.ModelAdmin):
    """
    Admin for CaseNote model.
    
    READ-ONLY: Notes are append-only in the system.
    """
    
    list_display = ['short_id', 'case_link', 'author_display', 'author_level', 'short_text', 'created_at']
    list_filter = ['author_level', 'created_at']
    search_fields = ['case__id', 'author__identifier', 'note_text']
    ordering = ['-created_at']
    list_select_related = ['case', 'author']
    
    readonly_fields = ['id', 'case', 'author', 'author_level', 'note_text', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Note Information', {
            'fields': ('id', 'case', 'author', 'author_level'),
        }),
        ('Content', {
            'fields': ('note_text',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def short_id(self, obj):
        return str(obj.id)[:8] + '...'
    short_id.short_description = 'ID'
    
    def case_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:reports_case_change', args=[obj.case.id])
        return format_html('<a href="{}">Case: {}</a>', url, str(obj.case.id)[:8])
    case_link.short_description = 'Case'
    
    def author_display(self, obj):
        return obj.author.identifier if obj.author else '-'
    author_display.short_description = 'Author'
    
    def short_text(self, obj):
        text = obj.note_text or ''
        return text[:50] + '...' if len(text) > 50 else text
    short_text.short_description = 'Note'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return True  # View only
    
    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================================
# CASE STATUS HISTORY ADMIN (FULLY READ-ONLY)
# =============================================================================

@admin.register(CaseStatusHistory)
class CaseStatusHistoryAdmin(admin.ModelAdmin):
    """
    Admin for CaseStatusHistory model.
    
    FULLY READ-ONLY: History is immutable.
    """
    
    list_display = [
        'short_id',
        'case_link',
        'level_transition',
        'status_transition',
        'is_auto_escalation_badge',
        'changed_by_display',
        'created_at',
    ]
    list_filter = ['to_status', 'to_level', 'is_auto_escalation', 'created_at']
    search_fields = ['case__id', 'changed_by__identifier', 'reason']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    list_select_related = ['case', 'changed_by']
    
    readonly_fields = [
        'id', 'case', 'from_status', 'to_status', 'from_level', 'to_level',
        'changed_by', 'reason', 'is_auto_escalation', 'created_at', 'updated_at',
    ]
    
    fieldsets = (
        ('History Entry', {
            'fields': ('id', 'case'),
        }),
        ('Level Transition', {
            'fields': ('from_level', 'to_level'),
        }),
        ('Status Transition', {
            'fields': ('from_status', 'to_status'),
        }),
        ('Change Details', {
            'fields': ('changed_by', 'reason', 'is_auto_escalation'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def short_id(self, obj):
        return str(obj.id)[:8] + '...'
    short_id.short_description = 'ID'
    
    def case_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:reports_case_change', args=[obj.case.id])
        return format_html('<a href="{}">Case: {}</a>', url, str(obj.case.id)[:8])
    case_link.short_description = 'Case'
    
    def level_transition(self, obj):
        """Display level transition with arrow."""
        from_lvl = f"L{obj.from_level}" if obj.from_level is not None else '—'
        to_lvl = f"L{obj.to_level}" if obj.to_level is not None else '—'
        if from_lvl != to_lvl:
            return format_html(
                '<span style="color: #e67e22; font-weight: bold;">{} → {}</span>',
                from_lvl, to_lvl
            )
        return f"{from_lvl} → {to_lvl}"
    level_transition.short_description = 'Level'
    
    def status_transition(self, obj):
        """Display status transition with arrow."""
        from_st = obj.from_status or '—'
        to_st = obj.to_status or '—'
        return f"{from_st} → {to_st}"
    status_transition.short_description = 'Status'
    
    def is_auto_escalation_badge(self, obj):
        """Display auto-escalation as badge."""
        if obj.is_auto_escalation:
            return format_html(
                '<span style="background-color: #f39c12; color: white; padding: 2px 6px; '
                'border-radius: 3px; font-size: 10px;">AUTO</span>'
            )
        return format_html('<span style="color: #7f8c8d;">Manual</span>')
    is_auto_escalation_badge.short_description = 'Type'
    
    def changed_by_display(self, obj):
        return obj.changed_by.identifier if obj.changed_by else '-'
    changed_by_display.short_description = 'Changed By'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False  # Completely read-only
    
    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================================
# LEGACY REPORT ADMIN
# =============================================================================

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Admin for legacy Report model."""
    
    list_display = ['report_number', 'status', 'priority', 'jurisdiction_code', 'submitted_at', 'assigned_to']
    list_filter = ['status', 'priority', 'jurisdiction_code', 'submitted_at']
    search_fields = ['id', 'report_number', 'jurisdiction_code']
    readonly_fields = ['id', 'report_number', 'created_at', 'updated_at', 'submitted_at', 
                       'encrypted_title', 'encrypted_content', 'encryption_key_id']
    
    fieldsets = (
        ('Report Info', {'fields': ('id', 'report_number', 'status', 'priority', 'jurisdiction_code')}),
        ('Assignment', {'fields': ('submitted_by', 'assigned_to')}),
        ('Encrypted Content', {'fields': ('encrypted_title', 'encrypted_content', 'encryption_key_id')}),
        ('Timestamps', {'fields': ('submitted_at', 'created_at', 'updated_at')}),
    )


@admin.register(ReportStatusHistory)
class ReportStatusHistoryAdmin(admin.ModelAdmin):
    """Admin for ReportStatusHistory model."""
    
    list_display = ['id', 'report', 'from_status', 'to_status', 'changed_by', 'created_at']
    list_filter = ['to_status', 'created_at']
    search_fields = ['report__report_number', 'changed_by__identifier']
    readonly_fields = ['id', 'report', 'from_status', 'to_status', 'changed_by', 'reason', 'created_at', 'updated_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReportNote)
class ReportNoteAdmin(admin.ModelAdmin):
    """Admin for ReportNote model."""
    
    list_display = ['id', 'report', 'author', 'is_private', 'created_at']
    list_filter = ['is_private', 'created_at']
    search_fields = ['report__report_number', 'author__identifier', 'content']
    readonly_fields = ['id', 'created_at', 'updated_at']


# =============================================================================
# INCIDENT MEDIA ADMIN (READ-ONLY with Download)
# =============================================================================

@admin.register(IncidentMedia)
class IncidentMediaAdmin(admin.ModelAdmin):
    """
    Admin for IncidentMedia model.
    
    STRICTLY READ-ONLY: Media files are immutable after upload.
    Admin can view and download files.
    """
    
    list_display = [
        'short_id',
        'incident_link',
        'media_type_badge',
        'file_size_display',
        'uploaded_by_display',
        'created_at',
        'download_link',
    ]
    list_filter = ['media_type', 'is_deleted', 'created_at']
    search_fields = ['id', 'incident__id', 'original_filename', 'uploaded_by__identifier']
    ordering = ['-created_at']
    list_select_related = ['incident', 'uploaded_by']
    
    # ALL fields read-only
    readonly_fields = [
        'id', 'incident', 'file', 'media_type', 'original_filename',
        'file_size', 'content_type', 'uploaded_by',
        'created_at', 'updated_at', 'is_deleted',
        'file_preview',
    ]
    
    fieldsets = (
        ('Identification', {
            'fields': ('id', 'incident'),
        }),
        ('File Details', {
            'fields': ('file', 'file_preview', 'media_type', 'original_filename', 'file_size', 'content_type'),
        }),
        ('Upload Info', {
            'fields': ('uploaded_by',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'is_deleted'),
            'classes': ('collapse',),
        }),
    )
    
    # === Display helpers ===
    
    def short_id(self, obj):
        """Display shortened UUID."""
        return str(obj.id)[:8] + '...'
    short_id.short_description = 'ID'
    short_id.admin_order_field = 'id'
    
    def incident_link(self, obj):
        """Link to the incident."""
        if obj.incident:
            from django.urls import reverse
            url = reverse('admin:reports_incident_change', args=[obj.incident.id])
            return format_html('<a href="{}">{}</a>', url, str(obj.incident.id)[:8] + '...')
        return '-'
    incident_link.short_description = 'Incident'
    
    def media_type_badge(self, obj):
        """Display media type with colored badge."""
        colors = {
            'photo': '#28a745',  # Green
            'video': '#007bff',  # Blue
        }
        color = colors.get(obj.media_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.media_type.upper()
        )
    media_type_badge.short_description = 'Type'
    media_type_badge.admin_order_field = 'media_type'
    
    def file_size_display(self, obj):
        """Display human-readable file size."""
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return '-'
    file_size_display.short_description = 'Size'
    file_size_display.admin_order_field = 'file_size'
    
    def uploaded_by_display(self, obj):
        """Display uploader identifier."""
        if obj.uploaded_by:
            return obj.uploaded_by.identifier
        return '-'
    uploaded_by_display.short_description = 'Uploaded By'
    uploaded_by_display.admin_order_field = 'uploaded_by__identifier'
    
    def download_link(self, obj):
        """Provide download link for the file."""
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank" style="color: #007bff;">📥 Download</a>',
                obj.file.url
            )
        return '-'
    download_link.short_description = 'Download'
    
    def file_preview(self, obj):
        """Show preview for images."""
        if obj.file and obj.media_type == 'photo':
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px; border: 1px solid #ccc;"/>',
                obj.file.url
            )
        elif obj.file and obj.media_type == 'video':
            return format_html(
                '<video controls style="max-width: 300px; max-height: 200px;"><source src="{}"></video>',
                obj.file.url
            )
        return 'No preview available'
    file_preview.short_description = 'Preview'
    
    # === Queryset ===
    
    def get_queryset(self, request):
        """Show ALL media records in admin, including soft-deleted ones."""
        return IncidentMedia.all_objects.all()
    
    # === Permissions ===
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        # Allow viewing but not editing
        return True
    
    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================================
# INVESTIGATION MESSAGE ADMIN (READ-ONLY)
# =============================================================================

@admin.register(InvestigationMessage)
class InvestigationMessageAdmin(admin.ModelAdmin):
    """
    Admin for InvestigationMessage model.
    
    STRICTLY READ-ONLY: Messages are immutable after creation.
    """
    
    list_display = [
        'short_id',
        'case_link',
        'sender_display',
        'sender_role',
        'message_type_badge',
        'short_text',
        'created_at',
    ]
    list_filter = ['sender_role', 'message_type', 'created_at']
    search_fields = ['case__id', 'sender__identifier', 'text_content']
    ordering = ['-created_at']
    list_per_page = 50
    list_select_related = ['case', 'sender']
    
    readonly_fields = [
        'id', 'case', 'sender', 'sender_role', 'message_type',
        'text_content', 'file', 'created_at', 'updated_at',
    ]
    
    fieldsets = (
        ('Message', {
            'fields': ('id', 'case', 'sender', 'sender_role', 'message_type'),
        }),
        ('Content', {
            'fields': ('text_content', 'file'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def short_id(self, obj):
        return str(obj.id)[:8] + '...'
    short_id.short_description = 'ID'
    
    def case_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:reports_case_change', args=[obj.case_id])
        return format_html('<a href="{}">{}</a>', url, str(obj.case_id)[:8] + '...')
    case_link.short_description = 'Case'
    
    def sender_display(self, obj):
        return obj.sender.identifier if obj.sender else 'SYSTEM'
    sender_display.short_description = 'Sender'
    
    def message_type_badge(self, obj):
        colors = {'text': '#3498db', 'media': '#e67e22', 'system': '#7f8c8d'}
        color = colors.get(obj.message_type, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.message_type.upper()
        )
    message_type_badge.short_description = 'Type'
    
    def short_text(self, obj):
        text = obj.text_content or ''
        return text[:50] + '...' if len(text) > 50 else text or '-'
    short_text.short_description = 'Content'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return True  # View only
    
    def has_delete_permission(self, request, obj=None):
        return False


# =============================================================================
# ESCALATION HISTORY ADMIN (READ-ONLY)
# =============================================================================

@admin.register(EscalationHistory)
class EscalationHistoryAdmin(admin.ModelAdmin):
    """
    Admin for EscalationHistory model.
    
    STRICTLY READ-ONLY: Escalation records are immutable audit entries.
    """
    
    list_display = [
        'short_id',
        'case_link',
        'event_type_badge',
        'level_transition',
        'escalation_type',
        'escalated_by_display',
        'assigned_officer_display',
        'created_at',
    ]
    list_filter = ['event_type', 'escalation_type', 'created_at']
    search_fields = ['case__id', 'escalated_by__identifier', 'assigned_officer__identifier', 'reason']
    ordering = ['-created_at']
    list_per_page = 50
    list_select_related = ['case', 'escalated_by', 'assigned_officer']
    
    readonly_fields = [
        'id', 'case', 'event_type', 'from_level', 'to_level',
        'escalation_type', 'escalated_by', 'assigned_officer',
        'reason', 'created_at', 'updated_at',
    ]
    
    fieldsets = (
        ('Event', {
            'fields': ('id', 'case', 'event_type', 'escalation_type'),
        }),
        ('Level Change', {
            'fields': ('from_level', 'to_level'),
        }),
        ('People', {
            'fields': ('escalated_by', 'assigned_officer'),
        }),
        ('Details', {
            'fields': ('reason',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def short_id(self, obj):
        return str(obj.id)[:8] + '...'
    short_id.short_description = 'ID'
    
    def case_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:reports_case_change', args=[obj.case_id])
        return format_html('<a href="{}">{}</a>', url, str(obj.case_id)[:8] + '...')
    case_link.short_description = 'Case'
    
    def event_type_badge(self, obj):
        colors = {'escalation': '#e74c3c', 'assignment': '#3498db'}
        color = colors.get(obj.event_type, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.event_type.upper()
        )
    event_type_badge.short_description = 'Event'
    
    def level_transition(self, obj):
        if obj.from_level and obj.to_level:
            return f'{obj.from_level} → {obj.to_level}'
        return '-'
    level_transition.short_description = 'Level Change'
    
    def escalated_by_display(self, obj):
        return obj.escalated_by.identifier if obj.escalated_by else 'AUTO'
    escalated_by_display.short_description = 'By'
    
    def assigned_officer_display(self, obj):
        return obj.assigned_officer.identifier if obj.assigned_officer else '-'
    assigned_officer_display.short_description = 'Assigned To'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return True  # View only
    
    def has_delete_permission(self, request, obj=None):
        return False