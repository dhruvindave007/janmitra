You enforce strict backend architecture.

CASE LIFECYCLE:
NEW → ASSIGNED → IN_PROGRESS → ESCALATED → RESOLVED → CLOSED

LEVEL FLOW:
L1 → L0 → L3 → L4

POLICE HIERARCHY:
Station Level:
- L0 → field officer
- L1 → PSO (assigns L0)
- L2 → PI (station head)
Regional:
- L3 → controls multiple stations via assigned_stations M2M
Zone:
- L4 → full zone access (global)

ESCALATION:
- Trigger when current time >= sla_deadline
- Do not escalate already escalated cases
- Do not escalate closed or resolved cases
- L0/L1/L2 → L3, L3 → L4
- L4 is final (no SLA deadline)

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
- L1/L2: cases in their police station only
- L3: escalated cases (L3/L4 level) from assigned_stations only
- L4: ALL cases (full global access)
- JANMITRA: no case list access

NOTIFICATION SCOPING:
- L1/L2: only users at the case's police station
- L3: only L3 users whose assigned_stations includes the station
- L4: all L4 users
- Never broadcast globally

DO NOT:
- Introduce unnecessary abstractions
- Split logic across multiple layers unnecessarily
- Add extra models or complexity