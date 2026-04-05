---
description: "Scaffold a new Django REST Framework API endpoint for JanMitra following the thin-view / service pattern."
argument-hint: "Describe the endpoint: e.g. 'POST /cases/{id}/reopen/ — L2+ can reopen a rejected case'"
agent: "agent"
---

Scaffold a new Django REST Framework endpoint for JanMitra.

**Endpoint spec:** ${input}

Follow these rules exactly:

1. **View** (`backend/reports/views.py`) — keep it thin:
   - Parse and validate request inputs
   - Check role permission using the appropriate class from `authentication/permissions.py`
   - Call the service method
   - Return the correct HTTP status code

2. **Service** — add the method to the relevant `backend/reports/services/*.py` file:
   - Use `transaction.atomic()` around all multi-step writes
   - Use `select_for_update()` when reading a Case for modification
   - Reject action if case is in a terminal state: `SOLVED`, `CLOSED`, `REJECTED`, `RESOLVED`
   - Do not allow `current_level` to decrease
   - Send station-scoped notifications via `notifications/services.py` — never global broadcast

3. **URL** — register in `backend/reports/incident_urls.py` (case endpoints) or `urls.py` (report endpoints)

4. **Permissions** — attach `IsAuthenticated` plus the correct role permission class

5. **HTTP status codes** — `200`/`201` success, `400` validation error, `403` permission denied, `404` not found, `409` conflict (e.g. duplicate assignment)

Output complete, working code for all affected files — no placeholders, no TODOs.
