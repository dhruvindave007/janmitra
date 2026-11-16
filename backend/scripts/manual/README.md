# Manual scripts

These scripts predate the automated test suite. They talk to a **running** server over HTTP
(`http://localhost:8000`) and create data in whatever database that server uses, so they are not
run by `manage.py test`.

```bash
cd backend
python manage.py runserver &
PYTHONPATH=. python scripts/manual/test_full_api.py
```

The automated, isolated tests live next to each app (`backend/*/tests/`).
