# JanMitra — Workspace Instructions

JanMitra is a **production-grade police incident command system** for Ahmedabad Police.
Stack: **Django REST Framework** (Python 3.11) + **Flutter** (Dart) unified mobile app.

## Architecture at a Glance

```
janmitra/
├── backend/           — Django REST Framework + PostgreSQL + Redis + Celery
├── janmitra_mobile/   — ONE unified Flutter app (citizen + ALL authority roles)
├── mobile/            — DEPRECATED — do NOT touch
├── .ai/               — Detailed AI context: system_prompt.md + skills/
└── docker/            — Docker configs
```

Detailed rules per layer → `.ai/skills/architecture.md`, `.ai/skills/backend.md`, `.ai/skills/flutter.md`

## Case Lifecycle

```
NEW → ASSIGNED → IN_PROGRESS → SOLVED → CLOSED
                             ↘ ESCALATED (SLA breach)
                             ↘ REJECTED (L2+)
```

Terminal states: `SOLVED`, `CLOSED`, `REJECTED`, `RESOLVED`  
SLA: 48h per level except L4 (no SLA). `current_level` is monotonic — never decreases.

## Police Role Hierarchy

| Role | Type | Access |
|------|------|--------|
| L0 | Field Officer (station) | Assigned cases only |
| L1 | PSO (station) | All cases at their station |
| L2 | PI / Station Head (station) | All cases at their station |
| L3 | Regional authority | Escalated cases from assigned_stations |
| L4 | Zonal authority | ALL cases globally |
| JANMITRA | Citizen | Own submitted cases only |

## Non-Negotiable Rules

**Never do these:**
- Modify `mobile/` — it is deprecated; the active app is `janmitra_mobile/`
- Add new Django models — use existing: `User`, `Case`, `Incident`, `InvestigationMessage`, etc.
- Broadcast notifications globally — always scope by station
- Decrease `case.current_level` — it is monotonic (once L3/L4, stays there)
- Use `CaseStatus.OPEN` in new code — it is legacy; check terminal states instead
- Create separate Flutter apps per role — ONE app with role-based routing
- Hardcode role names in Flutter UI — use `UserRoles.displayName()`
- Put business logic in views — it belongs in `reports/services/`

**Always do these:**
- Use `transaction.atomic()` for multi-step writes
- Use `select_for_update()` when modifying Case
- Validate roles and permissions before every action
- Scope notifications: L1/L2 → station, L3 → assigned_stations, L4 → all L4 users
- Wrap Flutter scrollable content in `SafeArea`
- Produce complete, working code in one response

## Build & Test Commands

```bash
# Backend
cd backend
python manage.py runserver     # Dev (set DEBUG=True on Windows: $env:DEBUG="True")
python manage.py test          # Run Django tests
docker-compose up              # Full Docker dev stack

# Flutter
cd janmitra_mobile
flutter analyze
flutter test
flutter build apk --debug
adb install -r build\app\outputs\flutter-apk\app-debug.apk
adb reverse tcp:8000 tcp:8000
```

## Test Users (password: `Test@1234`)

| Username | Role | Station |
|----------|------|---------|
| test_l0_alpha | L0 Field Officer | Test Station Alpha |
| test_l1_alpha | L1 PSO | Test Station Alpha |
| test_l2_alpha | L2 PI | Test Station Alpha |
| test_l3_user | L3 Regional | (assigned_stations M2M) |
| test_l4_user | L4 Zonal | (global) |
