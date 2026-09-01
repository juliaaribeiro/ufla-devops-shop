#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/ufla-devops-shop}"
TIMESTAMP="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP_FILE="${BACKUP_DIR}/postgres_${TIMESTAMP}.dump"

log() {
    echo "[$(date -Is)] $*"
}

if ! command -v pg_dump >/dev/null 2>&1; then
    echo "ERRO: pg_dump não encontrado." >&2
    exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERRO: defina DATABASE_URL antes de executar o backup." >&2
    exit 1
fi

mkdir -p "${BACKUP_DIR}"

log "Criando backup: ${BACKUP_FILE}"
pg_dump --format=custom --file="${BACKUP_FILE}" "${DATABASE_URL}"

log "Mantendo somente os 7 backups mais recentes"
mapfile -t backups < <(find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'postgres_*.dump' -printf '%T@ %p\n' | sort -nr | tail -n +8 | cut -d' ' -f2-)

for backup in "${backups[@]}"; do
    rm -f -- "${backup}"
    log "Backup antigo removido: ${backup}"
done

log "Backup concluído"
