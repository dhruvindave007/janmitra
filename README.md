# JanMitra - Government Intelligence Reporting System

**Production Demo Deployment Guide**

---

## 📁 Repository Structure

```
janmitra/
├── backend/                    # Django REST API
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── gunicorn.conf.py
│   ├── manage.py
│   ├── janmitra_backend/       # Django project settings
│   ├── authentication/         # User auth & JWT
│   ├── reports/                # Incident reports
│   ├── media_storage/          # Encrypted media handling
│   ├── escalation/             # Case escalation
│   ├── audit/                  # Audit logging
│   ├── notifications/          # Push notifications
│   └── core/                   # Shared utilities
│
├── mobile/                     # Flutter mobile app
│   ├── lib/
│   ├── android/
│   ├── ios/
│   └── pubspec.yaml
│
├── docker/                     # Docker configurations
│   └── nginx/
│       └── nginx.conf
│
├── docker-compose.yml          # Orchestration
├── docker-compose.prod.yml     # Production overrides
├── .env.example                # Environment template
├── .gitignore
├── .dockerignore
└── README.md
```

---

## ⚠️ NEVER COMMIT THESE FILES

| File/Folder | Reason |
|-------------|--------|
| `.env` | Contains secrets, API keys, passwords |
| `*.sqlite3` / `*.db` | Local database files |
| `encrypted_media/` | Sensitive incident media |
| `staticfiles/` | Generated static files |
| `venv/` / `.venv/` | Python virtual environments |
| `__pycache__/` | Python bytecode |
| `*.pyc` | Compiled Python |
| `logs/*.log` | Application logs |
| `*.pem` / `*.key` | SSL certificates/keys |
| `mobile/build/` | Flutter build artifacts |
| `.dart_tool/` | Dart tooling cache |

---

## 🚀 Quick Start (Development)

```bash
# Clone repository
git clone https://github.com/dhruvindave007/janmitra.git
cd janmitra

# Copy environment file
cp .env.example .env
# Edit .env with your values

# Start services
docker-compose up -d --build

# Access:
# API: http://localhost:8000/api/
# Admin: http://localhost:8000/admin/
```

---

## 🌐 Production Deployment

### Prerequisites
- Ubuntu 20.04+ server with public IP
- Docker & Docker Compose installed
- Minimum 2GB RAM, 20GB disk
- Ports 80, 443 open

### Step-by-Step Deployment

```bash
# 1. SSH into your server
ssh user@YOUR_SERVER_IP

# 2. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Log out and back in

# 3. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. Clone repository
git clone https://github.com/dhruvindave007/janmitra.git
cd janmitra

# 5. Create production .env
cp .env.example .env
nano .env  # Edit with production values

# 6. Build and start
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 7. Run migrations
docker-compose exec django python manage.py migrate

# 8. Create superuser
docker-compose exec django python manage.py createsuperuser

# 9. Collect static files
docker-compose exec django python manage.py collectstatic --noinput
```

### Test with Public IP
```bash
# API Health Check
curl http://YOUR_IP/api/health/

# Admin Panel
open http://YOUR_IP/admin/
```

---

## 🔒 Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `SECRET_KEY` | ✅ | Django secret key | `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DEBUG` | ✅ | Debug mode | `False` for production |
| `ALLOWED_HOSTS` | ✅ | Allowed hostnames | `your-domain.com,YOUR_IP` |
| `DATABASE_ENGINE` | ✅ | DB backend | `django.db.backends.postgresql` |
| `DATABASE_NAME` | ✅ | Database name | `janmitra_db` |
| `DATABASE_USER` | ✅ | Database user | `janmitra_user` |
| `DATABASE_PASSWORD` | ✅ | Database password | Strong password |
| `DATABASE_HOST` | ✅ | Database host | `db` (Docker service name) |
| `DATABASE_PORT` | ❌ | Database port | `5432` |
| `JWT_SECRET_KEY` | ✅ | JWT signing key | Different from SECRET_KEY |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | ❌ | Token expiry | `60` for demo |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | ❌ | Refresh token expiry | `7` |
| `MASTER_ENCRYPTION_KEY` | ✅ | Media encryption key | 32-byte base64 |
| `REDIS_URL` | ❌ | Redis connection | `redis://redis:6379/0` |
| `CSRF_TRUSTED_ORIGINS` | ✅ | Trusted origins for CSRF | `http://YOUR_IP,https://your-domain.com` |

---

## 🌍 Adding a Domain (Without Code Changes)

### 1. Update DNS
Point your domain's A record to your server's IP.

### 2. Update .env
```bash
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,YOUR_IP
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

### 3. Add SSL with Certbot
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate (stop nginx first)
docker-compose stop nginx
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# Update docker-compose.prod.yml to mount certificates
# Restart
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 📱 Mobile App Configuration

Update the API base URL in the Flutter app:

```dart
// lib/core/constants/api_constants.dart
class ApiConstants {
  // Development
  // static const String baseUrl = 'http://10.0.2.2:8000/api';
  
  // Production with IP
  static const String baseUrl = 'http://YOUR_IP/api';
  
  // Production with domain
  // static const String baseUrl = 'https://your-domain.com/api';
}
```

Build release APK:
```bash
cd mobile
flutter build apk --release
```

---

## 🔧 Maintenance Commands

```bash
# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f django
docker-compose logs -f nginx

# Restart services
docker-compose restart

# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ destroys data)
docker-compose down -v

# Database backup
docker-compose exec db pg_dump -U janmitra_user janmitra_db > backup_$(date +%Y%m%d).sql

# Database restore
cat backup.sql | docker-compose exec -T db psql -U janmitra_user janmitra_db

# Django shell
docker-compose exec django python manage.py shell

# Run tests
docker-compose exec django python manage.py test
```

---

## 📊 Demo Safety Checklist

- [ ] `DEBUG=False` in production
- [ ] Strong `SECRET_KEY` generated
- [ ] Different `JWT_SECRET_KEY`
- [ ] `ALLOWED_HOSTS` includes server IP/domain
- [ ] Database has strong password
- [ ] Media volume is persistent
- [ ] Static files collected
- [ ] Superuser created
- [ ] JWT tokens have reasonable lifetime (60 min for demo)
- [ ] CORS/CSRF configured for mobile app
- [ ] Rate limiting enabled

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    NGINX (Port 80/443)                  │
│  - Reverse proxy to Django                              │
│  - Serves static files                                  │
│  - Serves media files                                   │
│  - SSL termination (with domain)                        │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│              DJANGO + GUNICORN (Port 8000)              │
│  - REST API endpoints                                   │
│  - JWT Authentication                                   │
│  - Admin panel                                          │
│  - Business logic                                       │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│                   POSTGRESQL (Port 5432)                │
│  - Persistent data storage                              │
│  - User accounts, reports, audit logs                   │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│                     REDIS (Port 6379)                   │
│  - Celery task queue                                    │
│  - Caching layer                                        │
└─────────────────────────────────────────────────────────┘
```

---

## 📞 Support

For issues, create a GitHub issue or contact the development team.

**License:** Proprietary - Government of India
