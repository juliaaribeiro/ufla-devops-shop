#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALUES_FILE="$ROOT_DIR/monitoring/kube-prometheus-stack-values.yaml"

for command in kubectl helm; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Erro: '$command' não encontrado no PATH." >&2
    exit 1
  fi
done

CONTEXT="$(kubectl config current-context 2>/dev/null || true)"
if [[ -z "$CONTEXT" ]]; then
  echo "Erro: nenhum contexto Kubernetes está configurado." >&2
  exit 1
fi

if ! kubectl cluster-info >/dev/null 2>&1; then
  echo "Erro: não foi possível acessar o cluster do contexto '$CONTEXT'." >&2
  exit 1
fi

RAW_SERVICE="$(kubectl get service ufla-shop --namespace default --ignore-not-found -o name)"
HELM_SERVICES="$(kubectl get services --all-namespaces -l observability=ufla-shop -o name)"
if [[ -z "$RAW_SERVICE" && -z "$HELM_SERVICES" ]]; then
  echo "Erro: não encontrei a API instalada." >&2
  echo "Implante a aplicação e confirme a label observability=ufla-shop no Service." >&2
  exit 1
fi

echo "Contexto Kubernetes: $CONTEXT"
read -r -p "Instalar/atualizar observabilidade neste contexto? [y/N] " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
  echo "Operação cancelada."
  exit 0
fi

read -r -s -p "Defina uma senha inicial para o Grafana: " GRAFANA_PASSWORD
printf '\n'
if [[ -z "$GRAFANA_PASSWORD" ]]; then
  echo "Erro: a senha do Grafana não pode ser vazia." >&2
  exit 1
fi

umask 077
PASSWORD_FILE="$(mktemp)"
trap 'rm -f "$PASSWORD_FILE"' EXIT
printf '%s' "$GRAFANA_PASSWORD" >"$PASSWORD_FILE"
unset GRAFANA_PASSWORD

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
helm repo update
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values "$VALUES_FILE" \
  --set-file "grafana.adminPassword=$PASSWORD_FILE" \
  --wait \
  --timeout 15m

if [[ -n "$RAW_SERVICE" ]]; then
  kubectl apply -f "$ROOT_DIR/k8s/service.yaml"
  kubectl apply -f "$ROOT_DIR/monitoring/servicemonitor.yaml"
fi
kubectl apply -f "$ROOT_DIR/monitoring/prometheus-rules.yaml"
kubectl apply -f "$ROOT_DIR/monitoring/grafana-api-dashboard.yaml"

cat <<'EOF'

Observabilidade instalada.

Grafana:
  kubectl -n monitoring port-forward svc/prometheus-grafana 3000:80
  http://localhost:3000 (usuário: admin; senha: a que você informou)

Prometheus:
  kubectl -n monitoring port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090
  http://localhost:9090

Consulte docs/atividade-12.md para testar /metrics e simular o incidente.
EOF
