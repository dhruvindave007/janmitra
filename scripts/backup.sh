#!/bin/bash
# =============================================================================
# JANMITRA BACKUP SCRIPT
# =============================================================================

set -e

BACKUP_DIR="/backups/janmitra"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

echo "Starting backup at $DATE..."

# Backup database
echo "Backing up PostgreSQL database..."
docker-compose exec -T db pg_dump -U janmitra_user janmitra_db > "$BACKUP_DIR/db_$DATE.sql"

# Backup media files
echo "Backing up media files..."
docker run --rm -v janmitra_media:/data -v $BACKUP_DIR:/backup alpine tar czf /backup/media_$DATE.tar.gz -C /data .

# Keep only last 7 days of backups
echo "Cleaning old backups..."
find $BACKUP_DIR -name "db_*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "media_*.tar.gz" -mtime +7 -delete

echo "Backup completed!"
echo "Database: $BACKUP_DIR/db_$DATE.sql"
echo "Media: $BACKUP_DIR/media_$DATE.tar.gz"
