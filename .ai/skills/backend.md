You write production-ready Django REST Framework backend code for JanMitra.

## MANDATORY PRACTICES
- Use `transaction.atomic()` for multi-step writes
- Use `select_for_update()` when modifying Case
- Always validate roles before performing actions
- Always validate inputs (IDs, permissions, null checks)
- Handle edge cases safely
- Use `select_related` / `prefetch_related` to avoid N+1 queries

## CASE RULES
- status and current_level must always stay consistent
- current_level NEVER decreases (monotonicity: once at L3/L4, stays there)
- SLA uses `timezone.now()` — never naive datetime
- SLA is 48 hours per level (except L4 — no SLA)
- Do not allow duplicate L0 assignment
- Do not allow invalid escalation (terminal states block all actions)
- Terminal states: SOLVED, CLOSED, REJECTED, RESOLVED
- Do NOT check against CaseStatus.OPEN (it's legacy and unused)
- Check against terminal states instead: `if case.status in terminal: reject`

## SOLVE vs CLOSE FLOW
- SolveCaseView: any authority (L0+) can mark solved. Changes status→SOLVED, notifies L2 at station.
- CloseCaseView: only L2+ can close. Requires status==SOLVED first. Changes status→CLOSED, notifies L0.
- L0 "Mark as Solved" does NOT close the case.

## MEDIA HANDLING
- Accept only image (JPEG, PNG, GIF, WebP) and video (MP4, MOV, AVI, WebM)
- Max 3 files per incident; 10MB photos, 50MB videos
- Validate file type and size server-side
- Prevent unsafe uploads (no executable content types)

## NOTIFICATIONS (notifications/services.py)
- Send only to relevant users scoped by role + station:
  - L1/L2: users at the case's police_station (use `_get_station_officers`)
  - L3: users whose assigned_stations includes the station
  - L4: all L4 users
- Never broadcast globally
- Record notification in database
- Send FCM push when device_token exists
- Use `notify_case_solved_new` (station-scoped) not old `notify_case_solved` (global captains)

## BACKEND SERVICES (reports/services/)
All business logic lives in services, NOT in views:
- `BroadcastIncidentService.execute()` — Creates incident+case, GPS routing, media processing, notifications
- `AssignmentService.assign_officer()` — L1 assigns L0, validates station match, updates status
- `EscalationService.check_and_escalate()` — SLA breach detection, auto-escalate
- `InvestigationService.send_message()` — Chat messages with access control
- `JurisdictionService.find_nearest_station()` — Haversine GPS calculation

## INCIDENT CREATION (BroadcastIncidentService)
Accepts: user, text_content, category, latitude, longitude, media_files, area_name, city, state
Creates: Incident (immutable) + Case (status=NEW, level=L1, sla=48h) + IncidentMedia + system message
Routing: JurisdictionService finds nearest PoliceStation by GPS coordinates
Notifies: L1 and L2 at assigned police station

## KEY FILES
- `reports/models.py` — Case, Incident, CaseStatus, CaseLevel, InvestigationMessage, CaseNote, etc.
- `reports/views.py` — All API views (30+ endpoints)
- `reports/serializers.py` — CaseListSerializer, CaseDetailSerializer, etc. (area_name included)
- `reports/services/` — 5 service files with all business logic
- `reports/incident_urls.py` — Case lifecycle endpoints
- `authentication/models.py` — User model with roles, police_station FK, assigned_stations M2M
- `authentication/permissions.py` — IsJanMitra, IsLevel1OrLevel2, IsOfficer, etc.
- `notifications/services.py` — NotificationService with station-scoped + new workflow methods

## CODE QUALITY
- Keep logic inside services, not views
- Views are thin: parse request → call service → return response
- Avoid duplication across views
- Keep functions clear and maintainable
- Use transactions for anything that touches multiple tables