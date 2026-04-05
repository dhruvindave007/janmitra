---
name: janmitra-deploy
description: "JanMitra deployment workflow. Use when deploying to production, starting the Docker stack, running database migrations, performing health checks, or setting up the dev environment."
---

# JanMitra Deployment

## When to Use This Skill

- Starting the local development stack
- Deploying to production with Docker
- Running or rolling back database migrations
- Performing a health check on a running environment
- Setting up a new development machine

## Environments

| Environment | Entry Point | Backend URL |
|-------------|-------------|-------------|
| Local dev (direct) | `python manage.py runserver` | http://localhost:8000 |
| Local dev (Docker) | `docker-compose up` | http://localhost:8000 |
| Production | `docker-compose -f docker-compose.prod.yml up -d` | Nginx reverse proxy |

## Local Development Setup

### Backend (Windows)

```powershell
# 1. Activate Python env (if using venv)
cd backend

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment
$env:DEBUG = "True"
$env:DJANGO_SETTINGS_MODULE = "janmitra_backend.settings"

# 4. Apply migrations
python manage.py migrate

# 5. (Optional) Create superuser
python manage.py createsuperuser

# 6. Run dev server
python manage.py runserver
```

### Flutter Mobile

```bash
cd janmitra_mobile
flutter pub get
flutter run                     # Hot reload on connected device
adb reverse tcp:8000 tcp:8000   # Physical device port-forward
```

## Docker Stack

### Development

```bash
# Start full stack (Django + Postgres + Redis + Celery + Nginx)
docker-compose up

# Rebuild after dependency changes
docker-compose up --build

# Stop
docker-compose down

# Run Django management commands inside container
docker-compose exec django python manage.py migrate
docker-compose exec django python manage.py test
docker-compose exec django python manage.py shell
```

### Production

```bash
# Deploy
docker-compose -f docker-compose.prod.yml up -d --build

# Apply migrations in production
docker-compose -f docker-compose.prod.yml exec django python manage.py migrate

# View logs
docker-compose -f docker-compose.prod.yml logs -f django
docker-compose -f docker-compose.prod.yml logs -f celery

# Stop
docker-compose -f docker-compose.prod.yml down
```

## Database Migrations

```bash
# Inside container or directly
cd backend

# Generate migration after model change
python manage.py makemigrations <app>

# Apply all migrations
python manage.py migrate

# Rollback to a specific migration
python manage.py migrate <app> <migration_name>

# Preview SQL before applying
python manage.py sqlmigrate <app> <migration_name>

# Check for inconsistencies
python manage.py showmigrations
python manage.py check
```

## Health Checks

```bash
# API health endpoint (requires running stack)
curl http://localhost:8000/health/

# Script-based check
bash scripts/health-check.sh

# Database backup
bash scripts/backup.sh
```

## Environment Variables (`.env`)

Copy `.env.example` to `.env` and fill in:

| Variable | Purpose |
|----------|---------|
| `DEBUG` | `True` for dev, `False` for prod |
| `SECRET_KEY` | Django secret key |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `ALLOWED_HOSTS` | Comma-separated hosts |
| Firebase config | FCM push notifications |

**Never commit `.env` to source control.**

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/deploy.sh` | Automated production deployment |
| `scripts/backup.sh` | Database backup |
| `scripts/health-check.sh` | Service health check |
| `scripts/run_automation.ps1` | Windows automation helper |

## Flutter APK Build

```bash
cd janmitra_mobile
flutter build apk --debug
adb install -r build\app\outputs\flutter-apk\app-debug.apk
adb reverse tcp:8000 tcp:8000
```

Package: `com.example.janmitra_mobile`
