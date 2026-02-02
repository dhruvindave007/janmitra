#!/bin/bash
# =============================================================================
# JANMITRA HEALTH CHECK SCRIPT
# =============================================================================

echo "Checking JanMitra services..."
echo ""

# Check containers
echo "=== Container Status ==="
docker-compose ps

echo ""
echo "=== Health Checks ==="

# Check nginx
if curl -sf http://localhost/health/ > /dev/null; then
    echo "✓ NGINX: Healthy"
else
    echo "✗ NGINX: Unhealthy"
fi

# Check Django
if docker-compose exec -T django curl -sf http://localhost:8000/api/health/ > /dev/null; then
    echo "✓ Django: Healthy"
else
    echo "✗ Django: Unhealthy"
fi

# Check PostgreSQL
if docker-compose exec -T db pg_isready -U janmitra_user > /dev/null; then
    echo "✓ PostgreSQL: Healthy"
else
    echo "✗ PostgreSQL: Unhealthy"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null; then
    echo "✓ Redis: Healthy"
else
    echo "✗ Redis: Unhealthy"
fi

echo ""
echo "=== Disk Usage ==="
docker system df

echo ""
echo "=== Recent Errors ==="
docker-compose logs --tail=10 django | grep -i "error\|exception" || echo "No recent errors"
