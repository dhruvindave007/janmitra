#!/bin/bash
# =============================================================================
# JANMITRA DEPLOYMENT SCRIPT
# Fresh Ubuntu Server Setup
# =============================================================================

set -e

echo "=========================================="
echo "JANMITRA PRODUCTION DEPLOYMENT"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please run as non-root user with sudo privileges${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: System Update${NC}"
sudo apt update && sudo apt upgrade -y

echo -e "${YELLOW}Step 2: Install Docker${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${GREEN}Docker installed. Please log out and back in, then re-run this script.${NC}"
    exit 0
else
    echo -e "${GREEN}Docker already installed${NC}"
fi

echo -e "${YELLOW}Step 3: Install Docker Compose${NC}"
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi
echo -e "${GREEN}Docker Compose version: $(docker-compose --version)${NC}"

echo -e "${YELLOW}Step 4: Configure Firewall${NC}"
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo -e "${YELLOW}Step 5: Check .env file${NC}"
if [ ! -f .env ]; then
    echo -e "${RED}.env file not found!${NC}"
    echo "Please create .env from .env.example:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

echo -e "${YELLOW}Step 6: Build and Start Services${NC}"
docker-compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo -e "${YELLOW}Step 7: Wait for services to be healthy${NC}"
sleep 30

echo -e "${YELLOW}Step 8: Run Database Migrations${NC}"
docker-compose exec -T django python manage.py migrate

echo -e "${YELLOW}Step 9: Collect Static Files${NC}"
docker-compose exec -T django python manage.py collectstatic --noinput

echo -e "${YELLOW}Step 10: Create Superuser${NC}"
echo "Creating superuser (follow prompts):"
docker-compose exec django python manage.py createsuperuser

echo ""
echo -e "${GREEN}=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "==========================================${NC}"
echo ""
echo "Access your application at:"
echo "  API:    http://$(curl -s ifconfig.me)/api/"
echo "  Admin:  http://$(curl -s ifconfig.me)/admin/"
echo ""
echo "Check logs with:"
echo "  docker-compose logs -f"
echo ""
