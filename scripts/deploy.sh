#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ufla-devops-shop}"
VERSION="${1:-main}"
PORT="${PORT:-8000}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:${PORT}/health}"

log() {
    echo "[$(date -Is)] $*"
}

log "Iniciando deploy da versão ${VERSION}"

if [[ ! -d "${APP_DIR}/.git" ]]; then
    echo "ERRO: ${APP_DIR} não é um repositório Git." >&2
    exit 1
fi

cd "${APP_DIR}"

log "Atualizando código"
git fetch --all --quiet
git checkout "${VERSION}" --quiet
git pull --ff-only --quiet

log "Preparando ambiente Python"
python3 -m venv --upgrade-deps .venv
"${APP_DIR}/.venv/bin/pip" install -qr requirements.txt

log "Reiniciando serviço"
sudo systemctl restart ufla-devops-shop

log "Executando healthcheck"
if curl -fsS --retry 10 --retry-delay 1 "${HEALTH_URL}" >/dev/null; then
    log "Deploy da versão ${VERSION} concluído com sucesso"
    exit 0
fi

echo "ERRO: healthcheck não respondeu: ${HEALTH_URL}" >&2
exit 1
