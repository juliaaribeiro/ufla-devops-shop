#!/usr/bin/env bash
set -Eeuo pipefail

CLUSTER_NAME=ufla-shop
EVIDENCE_DIR=evidencia-atividade-09
IMAGE=ghcr.io/juliaaribeiro/ufla-shop
BASE_IMAGE="${IMAGE}:1.0.0"

mkdir -p "$EVIDENCE_DIR"
exec > >(tee -a "$EVIDENCE_DIR/execucao.log") 2>&1

cleanup() {
  local result=$?
  trap - EXIT
  set +e

  if kind get clusters | grep -Fxq "$CLUSTER_NAME"; then
    kubectl config use-context "kind-${CLUSTER_NAME}" >/dev/null 2>&1
    kubectl get nodes -o wide > "$EVIDENCE_DIR/nodes-final.txt" 2>&1
    kubectl get pods,deployments,services -A -o wide \
      > "$EVIDENCE_DIR/resources-final.txt" 2>&1
    kind export logs --name "$CLUSTER_NAME" "$EVIDENCE_DIR/kind-logs" \
      > "$EVIDENCE_DIR/kind-export-logs.txt" 2>&1
    kind delete cluster --name "$CLUSTER_NAME" \
      > "$EVIDENCE_DIR/kind-delete.txt" 2>&1
  fi

  exit "$result"
}
trap cleanup EXIT

kubectl version --client
kind version
docker version
kind create cluster \
  --name "$CLUSTER_NAME" \
  --config k8s/kind-config.yaml \
  --image kindest/node:v1.34.11@sha256:44e222ee2132dab25ff87301682f89eb82c7880ea3a1bf543bfe9708fd08d67d \
  --wait 5m
kubectl config use-context "kind-${CLUSTER_NAME}"

kubectl get nodes -o wide | tee "$EVIDENCE_DIR/nodes-initial.txt"
node_count=$(kubectl get nodes --no-headers | wc -l | tr -d ' ')
if [[ "$node_count" != 3 ]]; then
  printf 'Expected exactly 3 kind nodes, found %s.\n' "$node_count" >&2
  exit 1
fi

kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl wait --for=condition=available deployment/ufla-shop --timeout=180s
kubectl get deployment,service,pods -o wide \
  | tee "$EVIDENCE_DIR/initial-deployment.txt"
kubectl get endpoints ufla-shop \
  | tee "$EVIDENCE_DIR/service-endpoints.txt"

printf '\n=== Reconciliation after deleting one Pod ===\n'
mapfile -t old_pods < <(
  kubectl get pods -l app=ufla-shop -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'
)
old_pod=${old_pods[0]}
printf 'Deleting Pod: %s\n' "$old_pod"
start_ns=$(date +%s%N)
kubectl delete pod "$old_pod" --wait=false

replacement_pod=
for _ in $(seq 1 120); do
  while IFS= read -r candidate; do
    [[ -z "$candidate" ]] && continue
    if ! printf '%s\n' "${old_pods[@]}" | grep -Fxq "$candidate"; then
      replacement_pod=$candidate
      break
    fi
  done < <(
    kubectl get pods -l app=ufla-shop \
      -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'
  )
  [[ -n "$replacement_pod" ]] && break
  sleep 0.25
done

if [[ -z "$replacement_pod" ]]; then
  echo "No replacement Pod was created within 30 seconds." >&2
  exit 1
fi

kubectl get pod "$replacement_pod" -o wide \
  | tee "$EVIDENCE_DIR/replacement-pod-born.txt"
kubectl get pod "$replacement_pod" \
  -o jsonpath='created={.metadata.creationTimestamp}{"\n"}' \
  | tee -a "$EVIDENCE_DIR/replacement-pod-born.txt"
kubectl wait --for=condition=Ready "pod/$replacement_pod" --timeout=120s
end_ns=$(date +%s%N)
recreation_ms=$(((end_ns - start_ns) / 1000000))
printf 'Replica deleted: %s\nReplacement Pod: %s\nTime to Ready: %s ms\n' \
  "$old_pod" "$replacement_pod" "$recreation_ms" \
  | tee "$EVIDENCE_DIR/reconciliation-time.txt"
kubectl get events --sort-by=.metadata.creationTimestamp \
  | tee "$EVIDENCE_DIR/reconciliation-events.txt"

printf '\n=== Scale from 3 to 6 replicas ===\n'
kubectl scale deployment/ufla-shop --replicas=6
kubectl wait --for=jsonpath='{.status.readyReplicas}'=6 \
  deployment/ufla-shop --timeout=180s
kubectl get pods -l app=ufla-shop -o wide \
  | tee "$EVIDENCE_DIR/scaled-pods-by-node.txt"
kubectl get nodes -o wide | tee "$EVIDENCE_DIR/scaled-nodes.txt"

printf '\n=== Rollout to an image built from this commit ===\n'
new_image="${IMAGE}:sha-${GITHUB_SHA}"
docker build --pull -t "$new_image" .
docker image inspect "$new_image" \
  --format='Image={{index .RepoTags 0}} ID={{.Id}}' \
  | tee "$EVIDENCE_DIR/rollout-image.txt"
kind load docker-image "$new_image" --name "$CLUSTER_NAME"
kubectl set image deployment/ufla-shop "ufla-shop=$new_image"
kubectl rollout status deployment/ufla-shop --timeout=240s
kubectl get deployment/ufla-shop -o wide \
  | tee "$EVIDENCE_DIR/rollout-new-version.txt"

printf '\n=== Roll back to the previous image ===\n'
kubectl rollout undo deployment/ufla-shop
kubectl rollout status deployment/ufla-shop --timeout=240s
kubectl get deployment/ufla-shop -o wide \
  | tee "$EVIDENCE_DIR/rollout-undo.txt"
actual_image=$(kubectl get deployment/ufla-shop \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="ufla-shop")].image}')
if [[ "$actual_image" != "$BASE_IMAGE" ]]; then
  printf 'Expected rollback image %s, got %s.\n' "$BASE_IMAGE" "$actual_image" >&2
  exit 1
fi

restore_declarative_deployment() {
  kubectl delete -f "$1" --ignore-not-found=true --wait=true
  kubectl apply -f k8s/deployment.yaml
  kubectl wait --for=condition=available deployment/ufla-shop --timeout=180s
}

wait_for_container_reason() {
  local pod=$1
  local expected_reason=$2
  for _ in $(seq 1 120); do
    local reason
    reason=$(kubectl get pod "$pod" \
      -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || true)
    if [[ "$reason" == "$expected_reason" ]]; then
      return 0
    fi
    sleep 1
  done
  printf 'Pod %s did not reach expected state %s.\n' "$pod" "$expected_reason" >&2
  kubectl get pod "$pod" -o wide >&2 || true
  return 1
}

wait_for_pod_by_label() {
  local selector=$1
  local pod
  for _ in $(seq 1 60); do
    pod=$(kubectl get pods -l "$selector" \
      -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
    if [[ -n "$pod" ]]; then
      printf '%s\n' "$pod"
      return 0
    fi
    sleep 1
  done
  printf 'No Pod found for selector %s.\n' "$selector" >&2
  return 1
}

printf '\n=== Debug scenario: image inexistente ===\n'
kubectl apply -f k8s/debug/invalid-image.yaml
image_failure_pod=$(wait_for_pod_by_label app=ufla-shop-falha-imagem)
wait_for_container_reason "$image_failure_pod" ImagePullBackOff
printf '$ kubectl get pod %s -o wide\n' "$image_failure_pod"
kubectl get pod "$image_failure_pod" -o wide \
  | tee "$EVIDENCE_DIR/debug-invalid-image-status.txt"
printf '$ kubectl describe pod %s\n' "$image_failure_pod"
kubectl describe pod "$image_failure_pod" \
  | tee "$EVIDENCE_DIR/debug-invalid-image-describe.txt"
printf '$ kubectl logs %s --previous\n' "$image_failure_pod"
kubectl logs "$image_failure_pod" --previous \
  > "$EVIDENCE_DIR/debug-invalid-image-logs-previous.txt" 2>&1 || true
cat "$EVIDENCE_DIR/debug-invalid-image-logs-previous.txt"
kubectl get events --sort-by=.metadata.creationTimestamp \
  | tee "$EVIDENCE_DIR/debug-invalid-image-events.txt"
restore_declarative_deployment k8s/debug/invalid-image.yaml

printf '\n=== Debug scenario: comando inválido ===\n'
kubectl apply -f k8s/debug/invalid-command.yaml
command_failure_pod=$(wait_for_pod_by_label app=ufla-shop-falha-comando)
wait_for_container_reason "$command_failure_pod" CrashLoopBackOff
printf '$ kubectl get pod %s -o wide\n' "$command_failure_pod"
kubectl get pod "$command_failure_pod" -o wide \
  | tee "$EVIDENCE_DIR/debug-invalid-command-status.txt"
printf '$ kubectl describe pod %s\n' "$command_failure_pod"
kubectl describe pod "$command_failure_pod" \
  | tee "$EVIDENCE_DIR/debug-invalid-command-describe.txt"
printf '$ kubectl logs %s --previous\n' "$command_failure_pod"
kubectl logs "$command_failure_pod" --previous \
  | tee "$EVIDENCE_DIR/debug-invalid-command-logs-previous.txt"
restore_declarative_deployment k8s/debug/invalid-command.yaml

printf '\n=== Debug scenario: selector que não casa ===\n'
echo '$ kubectl apply -f k8s/debug/wrong-selector.yaml'
if kubectl apply -f k8s/debug/wrong-selector.yaml \
  > "$EVIDENCE_DIR/debug-wrong-selector-apply.txt" 2>&1; then
  cat "$EVIDENCE_DIR/debug-wrong-selector-apply.txt"
  echo "The mismatched selector manifest was unexpectedly accepted." >&2
  exit 1
else
  cat "$EVIDENCE_DIR/debug-wrong-selector-apply.txt"
fi
echo "The API rejected the Deployment; no broken resource was created."
kubectl get deployments -o wide \
  | tee "$EVIDENCE_DIR/debug-wrong-selector-status.txt"
kubectl get deployment ufla-shop-falha-selector \
  > "$EVIDENCE_DIR/debug-wrong-selector-resource.txt" 2>&1 || true
kubectl apply -f k8s/deployment.yaml
kubectl wait --for=condition=available deployment/ufla-shop --timeout=180s
kubectl get deployment/ufla-shop -o wide \
  | tee "$EVIDENCE_DIR/debug-corrections-complete.txt"

echo "All activity steps completed. Evidence is in $EVIDENCE_DIR/."
