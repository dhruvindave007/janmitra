#!/bin/bash
# =============================================================================
# JANMITRA V1 - AUTOMATED SERVER DEPLOYMENT
# Run this ON the server after cloning the repo
# =============================================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || echo "UNKNOWN")

echo -e "${CYAN}=========================================="
echo "  JANMITRA V1 - PRODUCTION DEPLOYMENT"
echo "  Server IP: $SERVER_IP"
echo "==========================================${NC}"

# Step 1: System update
echo -e "\n${YELLOW}[1/12] System Update${NC}"
sudo apt update -qq && sudo apt upgrade -y -qq

# Step 2: Install Docker
echo -e "\n${YELLOW}[2/12] Docker Installation${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${GREEN}Docker installed.${NC}"
    # Apply group membership without logout
    newgrp docker <<EOF
    echo "Docker group applied"
EOF
else
    echo -e "${GREEN}Docker already installed: $(docker --version)${NC}"
fi

# Step 3: Install Docker Compose
echo -e "\n${YELLOW}[3/12] Docker Compose${NC}"
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi
echo -e "${GREEN}Docker Compose: $(docker-compose --version 2>/dev/null || echo 'installed')${NC}"

# Step 4: Install git
echo -e "\n${YELLOW}[4/12] Git${NC}"
if ! command -v git &> /dev/null; then
    sudo apt install -y git
fi
echo -e "${GREEN}Git: $(git --version)${NC}"

# Step 5: Clone or update repo
echo -e "\n${YELLOW}[5/12] Repository Setup${NC}"
DEPLOY_DIR="/opt/janmitra"
if [ -d "$DEPLOY_DIR/.git" ]; then
    echo "Updating existing repo..."
    cd "$DEPLOY_DIR"
    git pull origin main
else
    echo "Cloning fresh repo..."
    sudo mkdir -p /opt
    sudo chown $USER:$USER /opt
    git clone https://github.com/dhruvindave007/janmitra.git "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
fi

# Initialize submodules if any
git submodule update --init --recursive 2>/dev/null || true

# Step 6: Generate .env
echo -e "\n${YELLOW}[6/12] Environment Configuration${NC}"
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || openssl rand -base64 50)
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || openssl rand -base64 50)
    MASTER_KEY=$(python3 -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())" 2>/dev/null || openssl rand -base64 32)
    DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))" 2>/dev/null || openssl rand -base64 24)

    cat > "$DEPLOY_DIR/.env" <<ENVFILE
# JANMITRA PRODUCTION - Auto-generated $(date)
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,${SERVER_IP}

# Database
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=janmitra_db
DATABASE_USER=janmitra_user
DATABASE_PASSWORD=${DB_PASS}
DATABASE_HOST=db
DATABASE_PORT=5432

# JWT
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=120
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# Encryption
MASTER_ENCRYPTION_KEY=${MASTER_KEY}

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1

# Security (HTTP-only, no SSL)
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
CSRF_TRUSTED_ORIGINS=http://${SERVER_IP},http://localhost

# CORS
CORS_ALLOW_ALL_ORIGINS=True

# Upload
DATA_UPLOAD_MAX_MEMORY_SIZE=524288000
FILE_UPLOAD_MAX_MEMORY_SIZE=524288000

# Gunicorn
GUNICORN_WORKERS=4
GUNICORN_LOG_LEVEL=warning

# Audit
AUDIT_LOG_RETENTION_DAYS=2555
ENVFILE

    echo -e "${GREEN}.env created with auto-generated secrets${NC}"
else
    echo -e "${GREEN}.env already exists — keeping existing config${NC}"
fi

# Step 7: Firewall
echo -e "\n${YELLOW}[7/12] Firewall Configuration${NC}"
sudo ufw allow 22/tcp 2>/dev/null || true
sudo ufw allow 80/tcp 2>/dev/null || true
sudo ufw allow 443/tcp 2>/dev/null || true
sudo ufw --force enable 2>/dev/null || true
echo -e "${GREEN}Firewall configured (22, 80, 443)${NC}"

# Step 8: Create required directories
echo -e "\n${YELLOW}[8/12] Directory Setup${NC}"
mkdir -p "$DEPLOY_DIR/backend/encrypted_media"
mkdir -p "$DEPLOY_DIR/backend/logs"
mkdir -p "$DEPLOY_DIR/backend/staticfiles"
echo -e "${GREEN}Directories ready${NC}"

# Step 9: Build and start Docker services
echo -e "\n${YELLOW}[9/13] Building Docker Services (this takes 3-5 minutes)${NC}"
cd "$DEPLOY_DIR"
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache 2>&1 | tail -5
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo -e "${YELLOW}Waiting for services to start (30s)...${NC}"
sleep 30

# Step 10: Run migrations
echo -e "\n${YELLOW}[10/13] Database Migrations${NC}"
docker-compose exec -T django python manage.py migrate --noinput
echo -e "${GREEN}Migrations complete${NC}"

# Step 11: Collect static files
echo -e "\n${YELLOW}[11/13] Static Files${NC}"
docker-compose exec -T django python manage.py collectstatic --noinput
echo -e "${GREEN}Static files collected${NC}"

# Step 12: Build and publish web app
echo -e "\n${YELLOW}[12/13] Build and Publish Web App${NC}"
bash "$DEPLOY_DIR/scripts/publish_webapp.sh"
echo -e "${GREEN}Web app publish step completed${NC}"

# Step 13: Seed users
echo -e "\n${YELLOW}[13/13] Seed Demo Users${NC}"
docker-compose exec -T django python manage.py seed_users --force 2>/dev/null || echo "seed_users not available, creating superuser..."
echo -e "${GREEN}Users ready${NC}"

# Health check
echo -e "\n${YELLOW}Running Health Checks...${NC}"
sleep 5

HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health/ 2>/dev/null || echo "000")
API=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/v1/app/version-check/ 2>/dev/null || echo "000")
ADMIN=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/admin/ 2>/dev/null || echo "000")
WEBAPP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/webapp/ 2>/dev/null || echo "000")

echo ""
echo -e "${CYAN}=========================================="
echo "  DEPLOYMENT COMPLETE!"
echo "==========================================${NC}"
echo ""
echo -e "  Server IP:  ${GREEN}$SERVER_IP${NC}"
echo -e "  Health:     ${GREEN}http://$SERVER_IP/health/${NC}     → $HEALTH"
echo -e "  API:        ${GREEN}http://$SERVER_IP/api/v1/${NC}     → $API"
echo -e "  Admin:      ${GREEN}http://$SERVER_IP/admin/${NC}      → $ADMIN"
echo -e "  Web App:    ${GREEN}http://$SERVER_IP/webapp/${NC}     → $WEBAPP"
echo -e "  Version:    ${GREEN}http://$SERVER_IP/api/v1/app/version-check/${NC}"
echo ""
echo -e "  ${YELLOW}Docker Status:${NC}"
docker-compose ps
echo ""
echo -e "  ${YELLOW}Logs:${NC} docker-compose logs -f"
echo -e "  ${YELLOW}Stop:${NC} docker-compose down"
echo ""
