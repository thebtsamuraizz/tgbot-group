#!/bin/bash
# Backup database script
# Creates timestamped backups and removes old ones

set -e

DB_FILE="${1:-.}"
BACKUP_DIR="${2:-backups}"
RETENTION_DAYS="${3:-30}"

# Get database filename
DB_FILENAME=$(basename "$DB_FILE")

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Create timestamped backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_FILENAME%.sqlite}_${TIMESTAMP}.backup"

echo "📦 Creating backup: $BACKUP_FILE"

if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "$BACKUP_FILE"
    echo "✅ Backup created successfully"
    ls -lh "$BACKUP_FILE"
else
    echo "❌ Error: Database file not found: $DB_FILE"
    exit 1
fi

# Remove backups older than RETENTION_DAYS
echo "🧹 Cleaning old backups (older than $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "${DB_FILENAME%.sqlite}_*.backup" -mtime +$RETENTION_DAYS -delete

# Show remaining backups
echo "📊 Current backups:"
ls -lh "$BACKUP_DIR" || echo "No backups found"

echo ""
echo "✨ Backup process completed"
