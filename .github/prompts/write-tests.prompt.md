---
description: "Generate Django unit and integration tests for JanMitra backend features. Covers role-based access, case lifecycle, SLA, notifications, and service logic."
argument-hint: "Describe what to test: e.g. 'SLA auto-escalation from L0/L1/L2 to L3 after 48h breach'"
agent: "agent"
---

Write Django tests for JanMitra.

**Test target:** ${input}

Follow these rules:

1. **Framework** — use `django.test.TestCase` or `rest_framework.test.APITestCase`

2. **Test file location** — `backend/<app>/tests/test_<feature>.py`

3. **Setup** — create test users matching the full role hierarchy:
   - L0 (`test_l0_alpha`) and L1 (`test_l1_alpha`) → assign `police_station` FK
   - L2 (`test_l2_alpha`) → assign `police_station` FK
   - L3 → assign `assigned_stations` M2M (at least one station)
   - L4 → no station required (global)
   - JANMITRA citizen → no station

4. **Test coverage** — for every feature, test:
   - ✅ Happy path (correct role, correct station, valid input)
   - ❌ Wrong role (403 expected)
   - ❌ Wrong station (403 or 404 expected)
   - ❌ Terminal state blocking action (400 or 403)
   - ❌ Invalid/missing inputs (400 expected)

5. **Case rules to verify:**
   - `current_level` never decreases (monotonicity)
   - Terminal states (`SOLVED`, `CLOSED`, `REJECTED`, `RESOLVED`) block all modifications
   - Solve ≠ Close (L0 solves, L2 closes — separate assertions)

6. **Notification tests** — assert station-scoped delivery:
   - L1/L2 notifications only reach users at the case's `police_station`
   - L3 notifications only reach users whose `assigned_stations` includes the station
   - No global broadcasts

7. **SLA tests** — mock `timezone.now()` to simulate time passing:
   ```python
   from unittest.mock import patch
   with patch('django.utils.timezone.now') as mock_now:
       mock_now.return_value = original_time + timedelta(hours=49)
       # trigger escalation check
   ```

Output complete, runnable Django test code — no placeholders, no TODOs.
