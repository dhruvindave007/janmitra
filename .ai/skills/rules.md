## GLOBAL RULES

### DO NOT
- Ask questions unless absolutely necessary
- Redesign system architecture
- Add new Django models (use existing: User, Case, Incident, InvestigationMessage, etc.)
- Use Celery (not needed yet)
- Use external APIs for GPS routing (haversine is local)
- Add unnecessary features beyond what's requested
- Decrease case current_level ever (monotonic: once L3/L4, stays there)
- Modify the `mobile/` directory (it's deprecated, use `janmitra_mobile/`)
- Create separate apps for different user roles (ONE unified app)
- Check against CaseStatus.OPEN in new workflow code (it's legacy)
- Hardcode role names in Flutter UI (use UserRoles.displayName())
- Broadcast notifications globally (always scope by station)

### ALWAYS
- Complete feature in one response
- Keep business logic inside services (reports/services/)
- Keep API views thin (parse request → call service → return response)
- Maintain consistency with existing structure and patterns
- Handle errors gracefully with proper HTTP status codes
- Respect role hierarchy: L0/L1/L2 = station, L3 = regional, L4 = global
- Scope notifications by station (not global broadcast)
- Use `transaction.atomic()` for multi-step writes
- Use `select_for_update()` when modifying Case
- Validate roles and permissions before every action
- Send area_name, city, state from citizen app via LocationResolver
- Use SafeArea in Flutter scrollable content
- Check terminal states {SOLVED, CLOSED, REJECTED, RESOLVED} instead of legacy OPEN

### WHEN UNCERTAIN
- Make safest assumption
- Prefer simple implementation over complex one
- Follow existing patterns in codebase

### TEST USERS (password: Test@1234)
- test_l0_alpha (L0, Test Station Alpha)
- test_l1_alpha (L1, Test Station Alpha)
- test_l2_alpha (L2, Test Station Alpha)
- test_l3_user (L3, regional)
- test_l4_user (L4, zonal)