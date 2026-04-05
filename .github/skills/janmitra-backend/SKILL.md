---
name: janmitra-backend
description: "JanMitra backend development workflow. Use when implementing Django REST Framework endpoints, writing or extending services, handling case lifecycle logic, fixing backend bugs, or reviewing Python/Django code."
---

# JanMitra Backend Development

## When to Use This Skill

- Implementing a new API endpoint
- Adding or modifying business logic in `reports/services/`
- Debugging case lifecycle issues
- Writing Django tests
- Reviewing backend code for correctness

## Procedure

### 1. Locate the Right Files

```
backend/
├── reports/views.py             — API views (keep thin)
├── reports/services/            — ALL business logic
│   ├── broadcast.py             — Incident + case creation
│   ├── assignment.py            — L1 assigns L0
│   ├── escalation.py            — SLA + auto-escalate
│   ├── investigation.py         — Chat messages
│   └── jurisdiction.py          — Haversine GPS routing
├── reports/serializers.py       — Response serializers
├── reports/incident_urls.py     — Case lifecycle endpoints
├── authentication/permissions.py — Role permission classes
└── notifications/services.py   — Station-scoped notifications
```

### 2. Pattern for a New Endpoint

**View** (`reports/views.py`):
```python
class MyNewView(APIView):
    permission_classes = [IsAuthenticated, IsLevel1OrLevel2]

    def post(self, request, case_id):
        case = get_object_or_404(Case, id=case_id)
        result = MyService.do_thing(request.user, case, request.data)
        return Response(result, status=status.HTTP_200_OK)
```

**Service** (`reports/services/my_service.py`):
```python
from django.db import transaction
from django.utils import timezone

class MyService:
    TERMINAL_STATES = {'solved', 'closed', 'rejected', 'resolved'}

    @classmethod
    @transaction.atomic
    def do_thing(cls, user, case, data):
        case = Case.objects.select_for_update().get(id=case.id)
        if case.status in cls.TERMINAL_STATES:
            raise ValidationError("Action not allowed on terminal case.")
        # ... logic here
```

**URL** (`reports/incident_urls.py`):
```python
path('cases/<uuid:case_id>/my-action/', MyNewView.as_view()),
```

### 3. Mandatory Checklist

- [ ] `transaction.atomic()` wraps multi-step writes
- [ ] `select_for_update()` on Case before modification
- [ ] Terminal states checked: `{SOLVED, CLOSED, REJECTED, RESOLVED}`
- [ ] `CaseStatus.OPEN` not referenced
- [ ] `current_level` not decreased
- [ ] Role permission class attached to view
- [ ] Notifications sent via `notifications/services.py` (station-scoped)
- [ ] `select_related` / `prefetch_related` used where needed
- [ ] All new models use UUID PK + BaseModel

### 4. Run and Test

```bash
cd backend

# Start dev server (Windows)
$env:DEBUG = "True"
python manage.py runserver

# Run tests
python manage.py test reports.tests
python manage.py test authentication.tests

# Django checks
python manage.py check

# Shell for debugging
python manage.py shell
```

## Key Constants

```python
# Case status
CaseStatus.NEW = 'new'
CaseStatus.ASSIGNED = 'assigned'
CaseStatus.IN_PROGRESS = 'in_progress'
CaseStatus.ESCALATED = 'escalated'
CaseStatus.SOLVED = 'solved'
CaseStatus.CLOSED = 'closed'
CaseStatus.REJECTED = 'rejected'
CaseStatus.RESOLVED = 'resolved'
# CaseStatus.OPEN = 'open'  ← LEGACY, do not use

# Case levels
CaseLevel.L0, L1, L2  # station-bound
CaseLevel.L3           # regional (assigned_stations M2M)
CaseLevel.L4           # zonal (global)
```

## Test Users (password: `Test@1234`)

| User | Role | Station |
|------|------|---------|
| test_l0_alpha | L0 | Test Station Alpha |
| test_l1_alpha | L1 | Test Station Alpha |
| test_l2_alpha | L2 | Test Station Alpha |
| test_l3_user | L3 | (assigned_stations) |
| test_l4_user | L4 | (global) |
