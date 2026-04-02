GLOBAL RULES:

DO NOT:
- Ask questions unless absolutely necessary
- Redesign system
- Add new models (assigned_stations M2M was the only approved addition)
- Use Celery (for now)
- Use external APIs for routing
- Add unnecessary features
- Decrease case current_level ever

ALWAYS:
- Complete feature in one response
- Keep logic inside services
- Keep API layer thin
- Maintain consistency with existing structure
- Handle errors gracefully
- Respect role hierarchy: L0/L1/L2 = station, L3 = regional, L4 = global
- Scope notifications by station (not global broadcast)

WHEN UNCERTAIN:
- Make safest assumption
- Prefer simple implementation over complex one