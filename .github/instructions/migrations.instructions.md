---
description: "Use when creating, reviewing, running, or rolling back Django database migrations. Covers safety patterns, rollback strategy, and JanMitra-specific model constraints."
---

# Django Migration Instructions

## Safety Rules

- Always create reversible migrations — test rollback before merging
- Never drop a column in the same release as the code that stops using it
- Never rename a column directly — add new column → backfill data → remove old column
- Never add a `NOT NULL` column to an existing table without a `default` value
- All new models must inherit `BaseModel` (UUID PK + `is_deleted` soft-delete)
- Never add auto-increment PKs — always use `UUIDField(primary_key=True, default=uuid.uuid4)`

## JanMitra-Specific Constraints

- `Case.current_level` is monotonic — no migration may relax this constraint
- `Incident` is immutable once created — do not add mutable fields to it
- `CaseStatusHistory` and `EscalationHistory` are append-only audit tables — do not add update hooks
- `InvestigationMessage` uses soft-delete only — never add hard-delete cascade

## Commands

```bash
cd backend

# Generate migration after model change
python manage.py makemigrations <app>

# Apply all pending migrations
python manage.py migrate

# Rollback to a specific migration
python manage.py migrate <app> <migration_name>

# Inspect migration state
python manage.py showmigrations

# Preview the SQL before applying
python manage.py sqlmigrate <app> <migration_name>

# Check for model/migration inconsistencies
python manage.py check
```

## Review Checklist

Before merging a migration PR:
- [ ] Migration is reversible (`reverse_sql` or `migrations.RunSQL` has reverse)
- [ ] No column drops in same release as code removal
- [ ] All new FKs have `on_delete` set explicitly
- [ ] New required fields have `default` or `null=True` for existing rows
- [ ] Migration file name is descriptive (`0005_add_area_name_to_incident`)
