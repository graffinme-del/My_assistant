#!/usr/bin/env sh
set -eu

STAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR=${BACKUP_DIR:-/opt/my_assistant/backups}
mkdir -p "${BACKUP_DIR}"

echo "Creating PostgreSQL backup..."
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" > "${BACKUP_DIR}/db_${STAMP}.sql"

echo "Creating MinIO archive..."
docker run --rm \
  -v my_assistant_minio_data:/data:ro \
  -v "${BACKUP_DIR}:/backup" \
  alpine sh -c "tar -czf /backup/minio_${STAMP}.tar.gz -C /data ."

echo "Backup completed: ${BACKUP_DIR}"
