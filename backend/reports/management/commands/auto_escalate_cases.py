"""
Django management command for SLA-based auto-escalation of cases.

This command finds all OPEN cases with expired SLAs and automatically
escalates them to the next level:
- Level 2 → Level 1
- Level 1 → Level 0
- Level 0 → (no further escalation)

Usage:
    python manage.py auto_escalate_cases
    python manage.py auto_escalate_cases --dry-run
    python manage.py auto_escalate_cases --verbose

This command is idempotent - running it multiple times will not
double-escalate cases that have already been escalated.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Auto-escalate cases with expired SLAs to the next level'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be escalated without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each case',
        )
    
    def handle(self, *args, **options):
        from reports.models import Case, CaseStatus, CaseLevel, CaseStatusHistory
        from audit.models import AuditLog, AuditEventType
        
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        now = timezone.now()
        
        self.stdout.write(
            self.style.NOTICE(f"Auto-escalation started at {now.isoformat()}")
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )
        
        # Find all cases that need escalation:
        # - Status is OPEN
        # - SLA deadline has passed
        # - Not already at Level-0 (can't escalate further)
        expired_cases = Case.objects.filter(
            status=CaseStatus.OPEN,
            sla_deadline__lt=now,
        ).exclude(
            current_level=CaseLevel.LEVEL_0
        ).select_for_update(skip_locked=True)
        
        # Count for reporting
        total_found = expired_cases.count()
        escalated_count = 0
        skipped_count = 0
        error_count = 0
        
        self.stdout.write(f"Found {total_found} cases with expired SLAs")
        
        for case in expired_cases:
            try:
                result = self._escalate_case(
                    case=case,
                    now=now,
                    dry_run=dry_run,
                    verbose=verbose,
                )
                if result:
                    escalated_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Error escalating case {case.id}: {str(e)}"
                    )
                )
        
        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Auto-escalation Summary ==="))
        self.stdout.write(f"  Total expired: {total_found}")
        self.stdout.write(f"  Escalated: {escalated_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        self.stdout.write(f"  Errors: {error_count}")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN - No actual changes were made")
            )
    
    def _escalate_case(self, case, now, dry_run, verbose):
        """
        Escalate a single case to the next level.
        
        Args:
            case: Case instance to escalate
            now: Current timestamp
            dry_run: If True, don't make changes
            verbose: If True, show detailed output
        
        Returns:
            bool: True if escalated, False if skipped
        """
        from reports.models import Case, CaseStatus, CaseLevel, CaseStatusHistory
        from audit.models import AuditLog, AuditEventType
        
        # Determine the next level
        old_level = case.current_level
        
        if old_level == CaseLevel.LEVEL_2:
            new_level = CaseLevel.LEVEL_1
        elif old_level == CaseLevel.LEVEL_1:
            new_level = CaseLevel.LEVEL_0
        else:
            # Already at Level-0, cannot escalate
            if verbose:
                self.stdout.write(
                    f"  Skipping case {str(case.id)[:8]}: Already at Level-0"
                )
            return False
        
        # Check if case can be escalated (double-check)
        can_escalate, reason = case.can_escalate()
        if not can_escalate:
            if verbose:
                self.stdout.write(
                    f"  Skipping case {str(case.id)[:8]}: {reason}"
                )
            return False
        
        # Check if SLA is actually expired (double-check for idempotency)
        if not case.is_sla_expired(now):
            if verbose:
                self.stdout.write(
                    f"  Skipping case {str(case.id)[:8]}: SLA not expired"
                )
            return False
        
        if verbose:
            self.stdout.write(
                f"  Escalating case {str(case.id)[:8]}: "
                f"Level {old_level} → Level {new_level}"
            )
        
        if dry_run:
            return True
        
        # Perform escalation within a transaction
        with transaction.atomic():
            # Re-fetch with lock for safety
            locked_case = Case.objects.select_for_update().get(pk=case.pk)
            
            # Double-check status hasn't changed
            if locked_case.status != CaseStatus.OPEN:
                if verbose:
                    self.stdout.write(
                        f"    Case {str(case.id)[:8]} status changed, skipping"
                    )
                return False
            
            # Double-check level hasn't changed
            if locked_case.current_level != old_level:
                if verbose:
                    self.stdout.write(
                        f"    Case {str(case.id)[:8]} level changed, skipping"
                    )
                return False
            
            # Update case
            locked_case.current_level = new_level
            locked_case.escalation_count += 1
            locked_case.last_escalated_at = now
            locked_case.sla_deadline = Case.calculate_sla_deadline_for_level(
                new_level, now
            )
            locked_case.save(update_fields=[
                'current_level', 'escalation_count', 
                'last_escalated_at', 'sla_deadline', 'updated_at'
            ])
            
            # Create status history entry
            CaseStatusHistory.objects.create(
                case=locked_case,
                from_status=CaseStatus.OPEN,
                to_status=CaseStatus.OPEN,
                from_level=old_level,
                to_level=new_level,
                changed_by=None,  # System action
                reason="SLA expired - auto-escalation",
                is_auto_escalation=True,
            )
            
            # Create audit log entry
            AuditLog.log(
                event_type=AuditEventType.CASE_ESCALATED,
                actor=None,  # System action
                target=locked_case,
                request=None,  # No HTTP request
                success=True,
                description=f"Case auto-escalated from Level-{old_level} to Level-{new_level}",
                metadata={
                    'case_id': str(locked_case.id),
                    'from_level': old_level,
                    'to_level': new_level,
                    'escalation_count': locked_case.escalation_count,
                    'new_sla_deadline': locked_case.sla_deadline.isoformat(),
                    'is_auto_escalation': True,
                    'reason': 'SLA expired',
                }
            )
        
        if verbose:
            self.stdout.write(
                self.style.SUCCESS(
                    f"    ✓ Escalated case {str(case.id)[:8]} to Level-{new_level}"
                )
            )
        
        return True
