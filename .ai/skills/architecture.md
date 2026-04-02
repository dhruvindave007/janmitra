You enforce strict backend architecture.

CASE LIFECYCLE:
NEW → ASSIGNED → IN_PROGRESS → ESCALATED → RESOLVED → CLOSED

LEVEL FLOW:
L1 → L0 → L3 → L4

ESCALATION:
- Trigger when current time >= sla_deadline
- Do not escalate already escalated cases
- Do not escalate closed or resolved cases

ASSIGNMENT:
- L1 assigns L0
- L0 must belong to same police station as case
- Only one active L0 per case

INVESTIGATION CHAT:
- One chat per case
- Messages are immutable
- System messages must be added for:
	- case creation
	- assignment
	- escalation

ACCESS CONTROL:
- L0: only assigned cases
- L1/L2: cases in their police station
- L3/L4: only escalated cases

DO NOT:
- Introduce unnecessary abstractions
- Split logic across multiple layers unnecessarily
- Add extra models or complexity