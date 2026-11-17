"""
Escalate cases whose SLA deadline has passed.

    python manage.py auto_escalate_cases
    python manage.py auto_escalate_cases --dry-run

Escalation path (see reports.services.escalation.EscalationService):

    L0 / L1 / L2 (station)  ->  L3  ->  L4 (final, no SLA)

In the Docker deployment the same logic runs on a schedule through Celery
beat (``reports.tasks.escalate_sla_breaches``). This command is for cron
based deployments and for running the job by hand.

The command is idempotent: an escalated case gets a fresh deadline, so a
second run straight afterwards finds nothing to do.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from reports.models import Case
from reports.services.escalation import EscalationService


class Command(BaseCommand):
    help = 'Escalate cases with an expired SLA to the next level'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List the cases that would be escalated without changing them',
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            breached = Case.objects.filter(
                status__in=EscalationService.ESCALATABLE_STATUSES,
                current_level__in=EscalationService.SLA_LEVELS,
                sla_deadline__lt=timezone.now(),
                is_deleted=False,
            ).order_by('sla_deadline')

            for case in breached:
                target = EscalationService.ESCALATION_MAP.get(case.current_level)
                self.stdout.write(
                    f'  would escalate {case.id}: {case.current_level} -> {target} '
                    f'(deadline {case.sla_deadline.isoformat()})'
                )
            self.stdout.write(self.style.WARNING(
                f'DRY RUN: {breached.count()} case(s) would be escalated'
            ))
            return

        escalated = EscalationService.process_sla_breaches()
        for case, from_level, to_level in escalated:
            self.stdout.write(f'  escalated {case.id}: {from_level} -> {to_level}')
        self.stdout.write(self.style.SUCCESS(f'Escalated {len(escalated)} case(s)'))
