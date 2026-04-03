## INFRASTRUCTURE & DEPLOYMENT

### Backend (Django)
- Python 3.x + Django REST Framework
- SQLite for development (postgres for production)
- Run: `cd backend && python manage.py runserver` (with `$env:DEBUG = "True"` on Windows)
- Settings module: `janmitra_backend.settings`
- Media files served at /media/ in DEBUG mode
- CORS configured for local development

### Flutter Mobile App
- ONE unified app: `janmitra_mobile/` (serves citizen + all authority roles)
- `mobile/` directory is DEPRECATED — do not modify
- Build: `cd janmitra_mobile && flutter build apk --debug`
- Deploy: `adb install -r build\app\outputs\flutter-apk\app-debug.apk`
- Port forward: `adb reverse tcp:8000 tcp:8000`
- Package name: `com.example.janmitra_mobile`
- Target device: Samsung S24 Ultra (ID: RZCY10L1SLA)
- ADB path: `C:\Users\daved\AppData\Local\Android\Sdk\platform-tools\adb.exe`

### Docker
- `docker-compose.yml` — Development setup
- `docker-compose.prod.yml` — Production setup
- Docker configs in `docker/` directory

### Database
- All models use UUID primary keys (no auto-increment)
- Soft delete everywhere via BaseModel (is_deleted flag)
- Django migrations managed normally

### Environment
- Windows development machine
- Backend: http://localhost:8000
- Flutter connects to 127.0.0.1:8000 (physical device needs adb reverse)
- Django shell: `$env:DEBUG = "True"; cd backend; python manage.py shell`

### FCM Push Notifications
- Firebase Cloud Messaging configured
- Device token registered via POST /api/v1/auth/device-token/
- Token sent after successful login
- Backend sends push via NotificationService when device_token exists on User