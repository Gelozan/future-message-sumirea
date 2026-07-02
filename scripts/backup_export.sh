#!/usr/bin/env bash
# Запускать с локального ПК:
# bash scripts/backup_export.sh <user>@<vps_ip>

set -euo pipefail

# ---------------------------------------------------------------------------
# Аргументы
# ---------------------------------------------------------------------------
if [[ $# -lt 1 ]]; then
  echo "Использование: bash scripts/backup_export.sh <user>@<vps_ip>"
  echo "Пример:        bash scripts/backup_export.sh deploy@123.45.67.89"
  exit 1
fi

SSH_TARGET="$1"
DATE=$(date +%Y-%m-%d)
BACKUP_NAME="backup_${DATE}"
LOCAL_DIR="./backups/${BACKUP_NAME}"

# ---------------------------------------------------------------------------
# Настройки — должны совпадать с .env на VPS
# ---------------------------------------------------------------------------
COMPOSE_PROJECT="future-message-sumirea"
PG_CONTAINER="fm_postgres"
MEDIA_VOLUME="${COMPOSE_PROJECT}_media_data"

# ---------------------------------------------------------------------------
echo "==> [1/4] Создаём локальную папку ${LOCAL_DIR}"
mkdir -p "${LOCAL_DIR}/media"

# ---------------------------------------------------------------------------
echo "==> [2/4] Дамп PostgreSQL через SSH"
ssh "${SSH_TARGET}" \
  "docker exec ${PG_CONTAINER} pg_dump -U \${POSTGRES_USER} -d \${POSTGRES_DB} -Fc" \
  > "${LOCAL_DIR}/db.dump"

echo "    Размер дампа: $(du -sh "${LOCAL_DIR}/db.dump" | cut -f1)"

# ---------------------------------------------------------------------------
echo "==> [3/4] Копирование медиафайлов через rsync"
# Используем временный контейнер alpine чтобы не лезть в /var/lib/docker напрямую
ssh "${SSH_TARGET}" \
  "docker run --rm -v ${MEDIA_VOLUME}:/data alpine tar czf - -C /data ." \
  > "${LOCAL_DIR}/media.tar.gz"

echo "    Размер медиа: $(du -sh "${LOCAL_DIR}/media.tar.gz" | cut -f1)"

# ---------------------------------------------------------------------------
echo "==> [4/4] Упаковка в финальный архив"
tar czf "./backups/${BACKUP_NAME}.tar.gz" -C "./backups" "${BACKUP_NAME}"
rm -rf "${LOCAL_DIR}"

echo ""
echo "✅ Готово: ./backups/${BACKUP_NAME}.tar.gz"
echo "   Размер: $(du -sh "./backups/${BACKUP_NAME}.tar.gz" | cut -f1)"
