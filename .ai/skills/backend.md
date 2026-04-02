You write production-ready Django backend code.

MANDATORY:
- Use transaction.atomic for multi-step writes
- Use select_for_update when modifying Case
- Always validate roles before performing actions
- Always validate inputs (IDs, permissions, null checks)
- Handle edge cases safely

CASE RULES:
- status and current_level must always stay consistent
- current_level must NEVER decrease (monotonicity)
- SLA must use timezone.now()
- SLA is 48 hours per level (except L4 — no SLA)
- Do not allow duplicate assignment
- Do not allow invalid escalation

MEDIA HANDLING:
- Accept only image and video
- Validate file type and size
- Prevent unsafe uploads

NOTIFICATIONS:
- Send only to relevant users scoped by role + station:
  - L1/L2: users at the case's police_station
  - L3: users whose assigned_stations includes the station
  - L4: all L4 users
- Never broadcast globally
- Record notification in database
- Send FCM push when device_token exists

CODE QUALITY:
- Keep logic inside services, not views
- Avoid duplication
- Keep functions clear and maintainable
- Use select_related / prefetch_related to avoid N+1 queries