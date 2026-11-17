"""Background jobs for the case lifecycle."""

import logging

from celery import shared_task

from reports.services.escalation import EscalationService

logger = logging.getLogger('janmitra.escalation')


@shared_task(name='reports.tasks.escalate_sla_breaches')
def escalate_sla_breaches():
    """
    Escalate every active case whose SLA deadline has passed.

    Safe to run repeatedly: escalation resets the deadline, so a case is
    only picked up again once the *new* level's SLA has also expired.
    """
    escalated = EscalationService.process_sla_breaches()
    for case, from_level, to_level in escalated:
        logger.info('SLA breach: case=%s %s -> %s', case.id, from_level, to_level)
    return len(escalated)
