---
description: "Review a complete JanMitra feature implementation for correctness: case logic, role permissions, notification scoping, transaction safety, and Flutter architecture."
argument-hint: "Describe the feature to review or paste the diff"
agent: "agent"
tools: [read, search]
---

Review the following JanMitra feature implementation for correctness.

**Feature to review:** ${input}

Check every item in this list and report any violations:

### Backend Checks
- [ ] Views are thin — business logic is in `reports/services/`, not in views
- [ ] All multi-step writes are wrapped in `transaction.atomic()`
- [ ] Case reads for modification use `select_for_update()`
- [ ] Terminal states (`SOLVED`, `CLOSED`, `REJECTED`, `RESOLVED`) block all actions
- [ ] `case.current_level` is never decreased
- [ ] `CaseStatus.OPEN` is not used in new code
- [ ] Notifications are station-scoped — no global broadcast
- [ ] Role permissions validated before every action
- [ ] Media: type + size validated server-side (≤10 MB photo, ≤50 MB video, max 3 per incident)
- [ ] UUIDs used for all new PKs (no auto-increment)

### Flutter Checks
- [ ] `mobile/` directory untouched
- [ ] Clean Architecture layers respected (domain → data → presentation)
- [ ] No new routes added for specific roles only — role guard used instead
- [ ] `SafeArea` wraps all scrollable content
- [ ] `UserRoles.displayName()` used for role labels
- [ ] New providers registered in `core/di/dependency_injection.dart`
- [ ] `AuthenticatedHttpClient` used for all HTTP calls
- [ ] `CaseStatus.OPEN` not used

### Architecture Checks
- [ ] No new Django models introduced
- [ ] No new Flutter apps or packages introduced without justification
- [ ] Existing patterns followed (no one-off abstractions)

Report each violation with: **file**, **line** (if applicable), and **what should be done instead**.
