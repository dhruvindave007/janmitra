You enforce the JanMitra system architecture strictly.

## PROJECT STRUCTURE
```
janmitra/
├── backend/                  — Django REST Framework API
│   ├── authentication/       — User, roles, JWT, device sessions
│   ├── reports/              — Incidents, Cases, Investigation chat, Media
│   │   ├── models.py         — Report, Incident, Case, CaseStatus, InvestigationMessage, etc.
│   │   ├── views.py          — All API views (reports + incidents + cases)
│   │   ├── serializers.py    — 16+ serializers
│   │   ├── services/         — Business logic (broadcast, assignment, escalation, investigation, jurisdiction)
│   │   ├── urls.py           — Report endpoints (/api/v1/reports/)
│   │   └── incident_urls.py  — Case endpoints (/api/v1/incidents/)
│   ├── notifications/        — Notification model, scoped delivery, FCM push
│   ├── escalation/           — Report escalation, identity reveal, decryption
│   ├── core/                 — BaseModel (UUID+soft-delete), PoliceStation
│   ├── audit/                — Security audit logging
│   └── media_storage/        — Media file management
├── janmitra_mobile/          — ONE unified Flutter app (citizen + authority)
│   └── lib/
│       ├── main.dart
│       ├── core/             — DI, HTTP client, router, services, constants
│       └── features/         — auth, broadcast, incidents, reports, dashboard, splash
├── mobile/                   — OLD citizen app (DEPRECATED, do not modify)
├── .ai/                      — AI context files (this folder)
└── docker/                   — Docker configs
```

## CASE LIFECYCLE
```
NEW → ASSIGNED (L1 assigns L0) → IN_PROGRESS → SOLVED (L0 marks) → CLOSED (L2 reviews & closes)
                                              ↘ ESCALATED (SLA breach: L0/L1/L2→L3→L4)
                                              ↘ REJECTED (L2+ rejects)
```
Terminal states: SOLVED, CLOSED, REJECTED, RESOLVED
Legacy status OPEN exists in code but is NOT used in new workflow.

## CASE STATUS CONSTANTS
NEW='new', ASSIGNED='assigned', IN_PROGRESS='in_progress', ESCALATED='escalated',
RESOLVED='resolved', OPEN='open' (LEGACY), SOLVED='solved', REJECTED='rejected', CLOSED='closed'

## CASE LEVEL CONSTANTS
L0 (Field Officer), L1 (PSO), L2 (PI), L3 (Regional), L4 (Zonal)
Station levels: [L0, L1, L2] — have police_station FK
Escalation levels: [L3, L4] — L3 has assigned_stations M2M, L4 is global

## LEVEL FLOW
L1 assigns L0 → L0 investigates → SLA breach escalates to L3 → then L4

## SOLVE vs CLOSE FLOW
1. L0 marks case as SOLVED (status→solved, notifies L2 at same station)
2. L2 reviews solved case → CLOSES it (status→closed, notifies L0)
3. L0 solve does NOT close the case

## ESCALATION
- Trigger: current time >= sla_deadline
- Do not escalate terminal cases (solved, closed, rejected, resolved)
- L0/L1/L2 → L3, L3 → L4
- L4 is final (no SLA deadline)
- current_level NEVER decreases (monotonic)

## ASSIGNMENT
- L1 assigns L0
- L0 must belong to same police station as case
- Only one active L0 per case
- Case status → ASSIGNED after assignment

## INVESTIGATION CHAT
- One thread per case (InvestigationMessage)
- Messages are immutable (no edit, soft-delete by author only)
- Three types: TEXT, MEDIA, SYSTEM
- System messages auto-created for: case creation, assignment, escalation, solve, close
- Chat can be locked (is_chat_locked on Case)
- Expandable UI: collapsed by default, red animated dot for unread, group chat style

## ACCESS CONTROL
- L0: only assigned cases
- L1/L2: cases in their police station only
- L3: escalated cases (L3/L4 level) from assigned_stations only
- L4: ALL cases (full global access)
- JANMITRA: only their own submitted cases

## NOTIFICATION SCOPING
- L1/L2: only users at the case's police station
- L3: only L3 users whose assigned_stations includes the station
- L4: all L4 users
- Never broadcast globally

## BACKEND SERVICES (reports/services/)
| Service | Purpose |
|---------|---------|
| broadcast.py | BroadcastIncidentService — create incident+case, GPS routing, media, notify |
| assignment.py | AssignmentService — L1 assigns L0, validates station match |
| escalation.py | EscalationService — SLA breach detection, auto-escalate |
| investigation.py | InvestigationService — chat messages, access control, system messages |
| jurisdiction.py | JurisdictionService — haversine GPS routing to nearest station |

## KEY API ENDPOINTS (reports/incident_urls.py)
```
POST   broadcast/                    — Citizen submits incident
GET    cases/                        — List cases (role-filtered)
GET    cases/open/                   — Active (non-terminal) cases
GET    cases/<id>/                   — Case detail
POST   cases/<id>/assign/            — L1 assigns L0
GET    cases/<id>/officers/          — Available L0 officers
POST   cases/<id>/solve/             — Mark solved (L0+)
POST   cases/<id>/close/             — Close solved case (L2+)
POST   cases/<id>/forward/           — Escalate case (Captain)
POST   cases/<id>/reject/            — Reject case (L2+)
POST   cases/<id>/notes/             — Add investigation note
GET    cases/<id>/messages/          — Investigation chat messages
POST   cases/<id>/messages/send/     — Send chat message
POST   cases/<id>/messages/media/    — Send media message
```

## FLUTTER APP ARCHITECTURE (janmitra_mobile)
- ONE app for ALL users (citizen + L0-L4)
- Role-based dashboard routing after login
- Clean Architecture: Data → Domain → Presentation per feature
- Provider pattern for state management
- Dependency injection via core/di/
- AuthenticatedHttpClient with JWT auto-refresh
- LocationResolver for reverse geocoding (area_name sent to backend)
- Offline support infrastructure (IncidentDraftStorage, NetworkMonitor)
- FCM push notifications registered after login

## FLUTTER ROLE → DASHBOARD ROUTING
```
JANMITRA → /janmitra-dashboard (submit incidents, view own cases)
L0       → /level0-dashboard (AuthorityCaseListScreen)
L1       → /level1-dashboard (AuthorityCaseListScreen)
L2       → /level2-dashboard (CaseListScreen + solve/close)
L3       → /level2-captain-dashboard (CaptainCaseListScreen)
L4       → /level2-captain-dashboard (CaptainCaseListScreen)
```
Role normalization: legacy names (level_0, level_2_captain) → canonical (L0, L2)

## DO NOT
- Introduce unnecessary abstractions
- Split logic across multiple layers unnecessarily
- Add extra models or complexity
- Modify the `mobile/` directory (deprecated)
- Use CaseStatus.OPEN in new workflow (it's legacy)