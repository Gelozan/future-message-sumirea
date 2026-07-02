#!/usr/bin/env bash
# Запускать с локального ПК перед новым сезоном:
# bash scripts/restore.sh <user>@<vps_ip> ./backups/backup_2026-07-15.tar.gz

set -euo pipefail

# ---------------------------------------------------------------------------
# Аргументы
# ---------------------------------------------------------------------------
if [[ $# -lt 2 ]]; then
  echo "Использование: bash scripts/restore.sh <user>@<vps_ip> <путь_к_архиву>"
  echo "Пример:        bash scripts/restore.sh deploy@123.45.67.89 ./backups/backup_2026-07-15.tar.gz"
  exit 1
fi

SSH_TARGET="$1"
ARCHIVE="$2"
COMPOSE_PROJECT="future-message-sumirea"
PG_CONTAINER="fm_postgres"
MEDIA_VOLUME="${COMPOSE_PROJECT}_media_data"
REMOTE_TMP="/tmp/fm_restore"

# ---------------------------------------------------------------------------
echo "==> [1/6] Распаковка архива локально"
TMPDIR=$(mktemp -d)
tar xzf "${ARCHIVE}" -C "${TMPDIR}"
BACKUP_DIR=$(find "${TMPDIR}" -mindepth 1 -maxdepth 1 -type d | head -1)

echo "    Архив: ${ARCHIVE}"
echo "    Дамп БД: $(du -sh "${BACKUP_DIR}/db.dump" | cut -f1)"
echo "    Медиа:   $(du -sh "${BACKUP_DIR}/media.tar.gz" | cut -f1)"

# ---------------------------------------------------------------------------
echo "==> [2/6] Загрузка файлов на VPS"
ssh "${SSH_TARGET}" "mkdir -p ${REMOTE_TMP}"
scp "${BACKUP_DIR}/db.dump"     "${SSH_TARGET}:${REMOTE_TMP}/db.dump"
scp "${BACKUP_DIR}/media.tar.gz" "${SSH_TARGET}:${REMOTE_TMP}/media.tar.gz"
rm -rf "${TMPDIR}"

# ---------------------------------------------------------------------------
echo "==> [3/6] Поднимаем контейнеры (только postgres)"
ssh "${SSH_TARGET}" "cd ~/future-message-sumirea && docker compose up -d postgres"
echo "    Ждём готовности postgres..."
sleep 10

# ---------------------------------------------------------------------------
echo "==> [4/6] Восстановление БД"
ssh "${SSH_TARGET}" "
  docker exec -i ${PG_CONTAINER} pg_restore \
    -U \${POSTGRES_USER} \
    -d \${POSTGRES_DB} \
    --clean --if-exists \
    < ${REMOTE_TMP}/db.dump
"

# ---------------------------------------------------------------------------
echo "==> [5/6] Восстановление медиафайлов"
ssh "${SSH_TARGET}" "
  docker run --rm \
    -v ${MEDIA_VOLUME}:/data \
    -v ${REMOTE_TMP}:/backup \
    alpine sh -c 'cd /data && tar xzf /backup/media.tar.gz'
"

# ---------------------------------------------------------------------------
echo "==> [6/6] Запуск всех сервисов"
ssh "${SSH_TARGET}" "cd ~/future-message-sumirea && docker compose up -d"
ssh "${SSH_TARGET}" "rm -rf ${REMOTE_TMP}"

echo ""
echo "✅ Восстановление завершено. Все сервисы запущены."
echo "   Проверь статус: ssh ${SSH_TARGET} 'docker compose ps'"
