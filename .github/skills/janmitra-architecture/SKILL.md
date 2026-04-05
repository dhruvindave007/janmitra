---
name: janmitra-architecture
description: "JanMitra system architecture reference. Use when designing new features, understanding the case lifecycle, checking role permissions, verifying notification scoping, or deciding where code belongs."
---

# JanMitra Architecture

## System Overview

JanMitra is a police incident command system for Ahmedabad Police.

- Citizens (JANMITRA) submit anonymous incident reports via mobile app
- Backend GPS-routes each report to the nearest police station
- Police officers (L0–L4 hierarchy) investigate, escalate, and close cases
- Full audit trail, SLA enforcement, and FCM push notifications

## Project Structure

```
janmitra/
├── backend/                    — Django REST Framework API
│   ├── authentication/         — User, roles, JWT, device sessions
│   ├── reports/                — Core: Incident, Case, InvestigationMessage, media
│   │   ├── services/           — ALL business logic lives here
│   │   ├── models.py
│   │   ├── views.py            — Thin views only
│   │   ├── serializers.py
│   │   ├── urls.py             — /api/v1/reports/
│   │   └── incident_urls.py    — /api/v1/incidents/ (case lifecycle)
│   ├── notifications/          — Notification model, FCM push, scoped delivery
│   ├── escalation/             — SLA breach detection, auto-escalate
│   ├── core/                   — BaseModel (UUID + soft-delete), PoliceStation
│   ├── audit/                  — Immutable audit logging
│   └── media_storage/          — Media file encryption + management
├── janmitra_mobile/lib/        — ONE unified Flutter app (all roles)
│   ├── core/                   — DI, HTTP client, router, services, constants
│   └── features/               — auth, broadcast, incidents, dashboard, splash
├── mobile/                     — DEPRECATED — do not modify
└── docker/                     — Docker configs
```

## Police Role Hierarchy

| Role | Station Binding | Access Scope |
|------|-----------------|-------------|
| L0 Field Officer | `police_station` FK | Only assigned cases |
| L1 PSO | `police_station` FK | All cases at station |
| L2 PI/Station Head | `police_station` FK | All cases at station |
| L3 Regional | `assigned_stations` M2M | Escalated cases from assigned stations |
| L4 Zonal | None (global) | All cases everywhere |
| JANMITRA | None | Own submitted cases only |

## Case Lifecycle

```
NEW → ASSIGNED (L1 assigns L0) → IN_PROGRESS → SOLVED (L0) → CLOSED (L2)
                                              ↘ ESCALATED (SLA 48h breach)
                                              ↘ REJECTED (L2+)
```

**Terminal states**: `SOLVED`, `CLOSED`, `REJECTED`, `RESOLVED` — all actions blocked.  
**`current_level`**: monotonic — never decreases.  
**`CaseStatus.OPEN`**: legacy value — do not use in new code.

## Case Level Constants

```
L0, L1, L2 → station-level (police_station FK)
L3          → regional (assigned_stations M2M)
L4          → zonal (global access)
```

## Escalation Rules

- Trigger: `timezone.now() >= case.sla_deadline`
- L0/L1/L2 → escalate to L3; L3 → escalate to L4
- L4 has no SLA (final level)
- Do not escalate terminal cases

## Notification Scoping (never global)

| Audience | Scope |
|----------|-------|
| L1/L2 | Users at `case.police_station` |
| L3 | L3 users whose `assigned_stations` includes the station |
| L4 | All L4 users |

## Key API Endpoints

```
POST   broadcast/                  — Citizen submits incident
GET    cases/                      — List cases (role-filtered)
GET    cases/<id>/                 — Case detail
POST   cases/<id>/assign/          — L1 assigns L0
POST   cases/<id>/solve/           — Mark solved (L0+)
POST   cases/<id>/close/           — Close solved case (L2+)
POST   cases/<id>/forward/         — Escalate (L3/L4)
POST   cases/<id>/reject/          — Reject case (L2+)
GET    cases/<id>/messages/        — Investigation chat
POST   cases/<id>/messages/send/   — Send chat message
```

## Backend Services (`reports/services/`)

| Service | Purpose |
|---------|---------|
| `BroadcastIncidentService.execute()` | Create incident + case, GPS routing, media, notify |
| `AssignmentService.assign_officer()` | L1 assigns L0, validates station match |
| `EscalationService.check_and_escalate()` | SLA breach → auto-escalate |
| `InvestigationService.send_message()` | Chat messages with access control |
| `JurisdictionService.find_nearest_station()` | Haversine GPS → nearest PoliceStation |

## Flutter Role → Screen Routing

```
JANMITRA → /janmitra-dashboard        → JanMitraDashboard
L0       → /level0-dashboard          → AuthorityCaseListScreen
L1       → /level1-dashboard          → AuthorityCaseListScreen
L2       → /level2-dashboard          → CaseListScreen
L3/L4    → /level2-captain-dashboard  → CaptainCaseListScreen
```

## Absolute Rules

- Never add new Django models
- Never modify `mobile/` (deprecated)
- Never broadcast notifications globally
- Never decrease `case.current_level`
- Never use `CaseStatus.OPEN` in new workflow code
- Keep logic in services — views are thin
