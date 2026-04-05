---
description: "Use when writing, reviewing, or modifying Django backend code. Covers DRF patterns, transaction safety, case rules, notification scoping, service layer, and media handling."
applyTo: "backend/**"
---

# Backend Instructions

Full backend practices → `.ai/skills/backend.md`

## Mandatory Transaction Patterns

- `transaction.atomic()` for ALL multi-step writes
- `select_for_update()` when reading a `Case` for modification
- `select_related` / `prefetch_related` to avoid N+1 queries
- `timezone.now()` for all datetime comparisons — never naive datetime

## Service Layer — Views Must Be Thin

All business logic lives in `backend/reports/services/`. Views only: parse request → call service → return response.

| Service | File | Responsibility |
|---------|------|----------------|
| `BroadcastIncidentService` | `broadcast.py` | Create incident + case, GPS routing, media, notify |
| `AssignmentService` | `assignment.py` | L1 assigns L0, validates station match |
| `EscalationService` | `escalation.py` | SLA breach detection, auto-escalate |
| `InvestigationService` | `investigation.py` | Chat messages with access control |
| `JurisdictionService` | `jurisdiction.py` | Haversine GPS → nearest PoliceStation |

## Case Rules

- **Terminal states**: `SOLVED`, `CLOSED`, `REJECTED`, `RESOLVED` — block ALL actions
- Never check `CaseStatus.OPEN` (legacy) — check terminal states instead
- `current_level` is monotonic — never set it lower
- Solve ≠ Close: L0 marks SOLVED → notifies L2; L2 reviews → CLOSES
- Only L1 assigns L0; L0 must belong to the same station as the case
- SLA: 48h per level except L4 (no SLA deadline)

## Notification Rules (`notifications/services.py`)

- L1/L2 notifications → `_get_station_officers()` (scoped to `case.police_station`)
- L3 notifications → users where `assigned_stations` includes the station
- L4 notifications → all L4 users
- Use `notify_case_solved_new` (station-scoped), not the old `notify_case_solved`
- Never broadcast globally

## Media Validation

- Accepted images: JPEG, PNG, GIF, WebP — max **10 MB**
- Accepted videos: MP4, MOV, AVI, WebM — max **50 MB**
- Max **3 files** per incident
- Validate file type AND size server-side; reject executable content types

## Model Conventions

- All PKs are UUIDs — never use auto-increment
- Soft delete via `BaseModel.is_deleted` — never hard-delete
- All new models must inherit `BaseModel`

## Key Files

| File | Contents |
|------|----------|
| `reports/models.py` | Case, Incident, InvestigationMessage, CaseNote, etc. |
| `reports/views.py` | All API views (thin) |
| `reports/serializers.py` | 16+ serializers |
| `reports/services/` | All business logic |
| `reports/incident_urls.py` | Case lifecycle endpoints |
| `authentication/models.py` | User with roles, police_station FK, assigned_stations M2M |
| `authentication/permissions.py` | IsJanMitra, IsLevel1OrLevel2, IsOfficer, etc. |
| `notifications/services.py` | Station-scoped notification delivery |
