#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://127.0.0.1:8080/api/erro}"
DURATION_SECONDS="${2:-780}"

if ! command -v curl >/dev/null 2>&1; then
  echo "Erro: curl não encontrado no PATH." >&2
  exit 1
fi
if [[ ! "$DURATION_SECONDS" =~ ^[0-9]+$ ]] || (( DURATION_SECONDS < 1 )); then
  echo "Erro: duração deve ser um inteiro positivo em segundos." >&2
  exit 1
fi

END_AT=$(( $(date +%s) + DURATION_SECONDS ))
COUNT=0
echo "Simulando 5xx em $URL por $DURATION_SECONDS segundos."
echo "Interrompa com Ctrl+C se precisar encerrar a simulação."

while (( $(date +%s) < END_AT )); do
  STATUS="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "$URL")"
  if [[ "$STATUS" != "500" ]]; then
    echo "Erro: esperado HTTP 500 em $URL, recebido HTTP $STATUS." >&2
    exit 1
  fi
  COUNT=$((COUNT + 1))
  printf '%s status=%s requisicoes=%s\n' "$(date -Is)" "$STATUS" "$COUNT"
  sleep 1
done

echo "Simulação encerrada: $COUNT respostas HTTP 500."
