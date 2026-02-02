# =============================================================================
# JANMITRA PRODUCTION DEPLOYMENT GUIDE
# Step-by-Step Instructions for Demo Deployment
# =============================================================================

## PHASE 1: REPOSITORY SETUP (Local Machine)

### 1.1 Current Structure Explained

```
c:\janmitra\
├── backend/                    ← Django REST API (Docker-ready)
│   ├── Dockerfile              ← Multi-stage production build
│   ├── requirements.txt        ← Python dependencies
│   ├── gunicorn.conf.py        ← Production WSGI server config
│   ├── manage.py               ← Django management
│   ├── janmitra_backend/       ← Django project settings
│   ├── authentication/         ← JWT auth, user management
│   ├── reports/                ← Incident reporting
│   ├── media_storage/          ← Encrypted media handling
│   ├── escalation/             ← Case escalation
│   ├── audit/                  ← Audit logging
│   ├── notifications/          ← Push notifications
│   └── core/                   ← Shared utilities
│
├── mobile/                     ← Flutter mobile app
│   ├── lib/                    ← Dart source code
│   ├── android/                ← Android build files
│   ├── ios/                    ← iOS build files
│   └── pubspec.yaml            ← Flutter dependencies
│
├── docker/                     ← Docker configurations
│   └── nginx/
│       └── nginx.conf          ← Reverse proxy config
│
├── scripts/                    ← Deployment scripts
│   ├── deploy.sh               ← Automated deployment
│   ├── backup.sh               ← Database backup
│   └── health-check.sh         ← Service health check
│
├── docker-compose.yml          ← Service orchestration
├── docker-compose.prod.yml     ← Production overrides
├── .env.example                ← Environment template
├── .gitignore                  ← Files to exclude from git
└── README.md                   ← Main documentation
```

### 1.2 What MUST NOT Be Committed

| File/Pattern | Why |
|--------------|-----|
| `.env` | Contains secrets |
| `*.sqlite3` | Development database |
| `encrypted_media/` | Sensitive incident media |
| `venv/` | Virtual environment |
| `__pycache__/` | Python cache |
| `mobile/build/` | Flutter build output |
| `*.pem`, `*.key` | SSL certificates |

### 1.3 Push to GitHub

```powershell
# From c:\janmitra
git init
git remote add origin https://github.com/dhruvindave007/janmitra.git
git add .
git commit -m "Production deployment setup"
git branch -M main
git push -u origin main
```

---

## PHASE 2: SERVER SETUP (Ubuntu 20.04+)

### 2.1 SSH Into Server

```bash
ssh username@YOUR_SERVER_IP
```

### 2.2 Install Docker & Docker Compose

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# IMPORTANT: Log out and back in for group changes
exit
# SSH back in

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify
docker --version
docker-compose --version
```

### 2.3 Configure Firewall

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS (for later)
sudo ufw enable
```

### 2.4 Clone Repository

```bash
cd /home/$USER
git clone https://github.com/dhruvindave007/janmitra.git
cd janmitra
```

---

## PHASE 3: ENVIRONMENT CONFIGURATION

### 3.1 Create .env File

```bash
cp .env.example .env
nano .env
```

### 3.2 Generate Secrets

```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Generate JWT_SECRET_KEY (DIFFERENT from SECRET_KEY)
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Generate MASTER_ENCRYPTION_KEY (32-byte base64)
python3 -c "import base64, secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"

# Generate DATABASE_PASSWORD
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3.3 Complete .env Example (Replace Values)

```env
# Django Core
SECRET_KEY=abc123yourGeneratedSecretKeyHere
DEBUG=False
ALLOWED_HOSTS=YOUR_SERVER_IP,localhost

# Database
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=janmitra_db
DATABASE_USER=janmitra_user
DATABASE_PASSWORD=YourStrongDatabasePassword123
DATABASE_HOST=db
DATABASE_PORT=5432

# JWT (60 min access for demo convenience)
JWT_SECRET_KEY=xyz789DifferentJwtSecretKeyHere
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=60
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# Encryption
MASTER_ENCRYPTION_KEY=YourBase64EncodedEncryptionKey==

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1

# Security (HTTP mode for IP-only demo)
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

# CSRF (CRITICAL for admin panel)
CSRF_TRUSTED_ORIGINS=http://YOUR_SERVER_IP,http://localhost

# CORS
CORS_ALLOW_ALL_ORIGINS=True
```

---

## PHASE 4: DEPLOY & START SERVICES

### 4.1 Build and Launch

```bash
# Build images and start containers
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# This will take 2-5 minutes on first run
```

### 4.2 Wait for Services

```bash
# Check container status
docker-compose ps

# All should show "Up" or "healthy"
# Wait until db and redis are healthy before proceeding
```

### 4.3 Run Database Migrations

```bash
docker-compose exec django python manage.py migrate
```

### 4.4 Collect Static Files

```bash
docker-compose exec django python manage.py collectstatic --noinput
```

### 4.5 Create Superuser

```bash
docker-compose exec django python manage.py createsuperuser
# Follow prompts: username, email, password
```

---

## PHASE 5: VERIFY DEPLOYMENT

### 5.1 Test Endpoints

```bash
# Health check
curl http://localhost/health/
# Expected: {"status": "healthy", "service": "janmitra-backend"}

# API root
curl http://localhost/api/v1/
# Expected: {"name": "JanMitra API", "version": "v1", ...}

# Test with public IP
curl http://YOUR_SERVER_IP/health/
curl http://YOUR_SERVER_IP/api/v1/
```

### 5.2 Access Admin Panel

Open in browser: `http://YOUR_SERVER_IP/admin/`
Login with superuser credentials.

### 5.3 Check Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f django
docker-compose logs -f nginx
```

---

## PHASE 6: MOBILE APP CONFIGURATION

### 6.1 Update API Base URL

Edit `mobile/lib/core/constants/api_constants.dart`:

```dart
class ApiConstants {
  // For IP-based demo
  static const String baseUrl = 'http://YOUR_SERVER_IP/api';
  
  // For domain (later)
  // static const String baseUrl = 'https://your-domain.com/api';
}
```

### 6.2 Build Release APK

```bash
cd mobile
flutter clean
flutter pub get
flutter build apk --release
```

APK location: `mobile/build/app/outputs/flutter-apk/app-release.apk`

---

## PHASE 7: ADDING A DOMAIN (Without Code Changes)

### 7.1 DNS Configuration

Point A record: `your-domain.com` → `YOUR_SERVER_IP`

### 7.2 Update .env

```bash
nano .env
```

Update these values:
```env
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,YOUR_SERVER_IP
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com,http://YOUR_SERVER_IP
```

### 7.3 Get SSL Certificate

```bash
# Stop nginx temporarily
docker-compose stop nginx

# Install Certbot
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# Certificates saved to /etc/letsencrypt/live/your-domain.com/
```

### 7.4 Update docker-compose.prod.yml

Add SSL volume mount to nginx service:
```yaml
nginx:
  volumes:
    - /etc/letsencrypt:/etc/letsencrypt:ro
```

### 7.5 Enable SSL in nginx.conf

Uncomment the SSL server block in `docker/nginx/nginx.conf` and update domain name.

### 7.6 Restart

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## DEMO SAFETY CHECKLIST

| Item | Status | Notes |
|------|--------|-------|
| DEBUG=False | ☐ | Never True in production |
| Strong SECRET_KEY | ☐ | 50+ characters |
| Different JWT_SECRET_KEY | ☐ | Separate from Django key |
| Database password | ☐ | 20+ characters |
| ALLOWED_HOSTS set | ☐ | Include IP and domain |
| CSRF_TRUSTED_ORIGINS set | ☐ | Must include http:// prefix |
| JWT lifetime reasonable | ☐ | 60 min for demo |
| Static files collected | ☐ | Admin panel CSS |
| Superuser created | ☐ | For admin access |
| Health check passing | ☐ | /health/ returns 200 |

---

## TROUBLESHOOTING

### Container won't start
```bash
docker-compose logs django
docker-compose logs db
```

### Admin panel no CSS
```bash
docker-compose exec django python manage.py collectstatic --noinput
```

### CSRF Error in Admin
Ensure `CSRF_TRUSTED_ORIGINS` includes `http://YOUR_IP` (with http:// prefix)

### Database connection error
Wait for db container to be healthy, then restart django:
```bash
docker-compose restart django
```

### Permission denied
```bash
sudo chown -R $USER:$USER /home/$USER/janmitra
```

---

## QUICK REFERENCE COMMANDS

```bash
# Start all
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Stop all
docker-compose down

# Restart
docker-compose restart

# View logs
docker-compose logs -f

# Django shell
docker-compose exec django python manage.py shell

# Database backup
docker-compose exec -T db pg_dump -U janmitra_user janmitra_db > backup.sql

# Check disk usage
docker system df
```
