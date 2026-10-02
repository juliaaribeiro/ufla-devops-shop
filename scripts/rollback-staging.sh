#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:?Uso: bash scripts/rollback-staging.sh <sha-commit|versao-semver>}"
COMPOSE_DIR="${COMPOSE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

if [[ ! "$IMAGE_TAG" =~ ^(sha-[0-9a-f]{40}|[0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
    echo "ERRO: informe uma tag sha-<commit> ou uma versao SemVer (X.Y.Z)." >&2
    exit 1
fi

cd "$COMPOSE_DIR"
IMAGE_TAG="$IMAGE_TAG" docker compose pull api
IMAGE_TAG="$IMAGE_TAG" docker compose up -d --wait

echo "Rollback concluido para ghcr.io/juliaaribeiro/ufla-shop:${IMAGE_TAG}"
