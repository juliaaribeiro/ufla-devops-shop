# Atividade 12 — Observabilidade e SRE

## Arquitetura identificada

A aplicação é FastAPI e expõe `GET /api/erro` para simulação controlada de 500.
O projeto já contém Deployment/Service Kubernetes e um chart Helm. O Service
usa a porta nomeada `http`; a API escuta na porta 8000. O endpoint de scrape é
`/metrics`. A readiness existente é `/ready` e a liveness é `/health`.

As métricas não incluem identificadores de usuário, sessão ou requisição:

- `http_requests_total{method,route,status}`: counter RED.
- `http_duration_seconds{method,route}`: histogram RED, usado para p95.
- `route` é o template de rota FastAPI, não o caminho preenchido com IDs.

## Instalação da observabilidade

Pré-requisitos: `kubectl`, `helm`, contexto Kubernetes funcional, aplicação já
implantada e Service com a label `observability: ufla-shop`. O script instala
somente kube-prometheus-stack e os recursos de monitoramento; não cria cluster,
não altera banco de dados e não aplica manifests de Deployment da aplicação.

```bash
chmod +x scripts/atividade-12-observability.sh
./scripts/atividade-12-observability.sh
```

O script mostra o contexto e pede confirmação antes de alterar o cluster. A
senha inicial do Grafana é lida sem eco e não fica em arquivo versionado. Para
o Deployment Kubernetes direto do projeto, atualize o Service antes:

```bash
kubectl apply -f k8s/service.yaml
```

Para a aplicação gerenciada pelo chart, sincronize a release após publicar a
branch `atividade-12`; o chart cria um ServiceMonitor por release. O script
aplica o ServiceMonitor central somente para `default`, onde ficam os recursos
da instalação direta. Não altere a branch das Applications Argo CD para
`atividade-12` sem revisar o impacto: elas também podem apontar para produção.

## Port-forward e verificação

Execute cada port-forward em um terminal separado:

```bash
kubectl -n monitoring port-forward svc/prometheus-grafana 3000:80
kubectl -n monitoring port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090
```

- Grafana: <http://localhost:3000>, usuário `admin`, senha definida no script.
- Prometheus: <http://localhost:9090>.
- Dashboard provisionado: **UFLA DevOps Shop — Observabilidade**.

Para a instalação Kubernetes direta do projeto:

```bash
kubectl -n default port-forward svc/ufla-shop 8080:80
curl -i http://127.0.0.1:8080/metrics
```

Para uma release Helm em staging, use o Service presente no cluster:

```bash
kubectl get services -n devops-staging
kubectl -n devops-staging port-forward svc/<service-da-api> 8080:80
```

Confirme no Prometheus **Status → Targets** que o target da API está `UP`.
Consultas para validar:

```promql
sum by (route) (rate(http_requests_total[5m]))
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
histogram_quantile(0.95, sum by (le, route) (rate(http_duration_seconds_bucket[5m])))
```

O painel de saturação usa consumo de CPU de cAdvisor dividido pelo limite de
CPU reportado por kube-state-metrics, para os containers da loja. Esse sinal
fica sem dados se o kubelet não publicar as métricas de container ou se não
houver limite de CPU no Deployment.

## Simulação e recuperação

Use somente um cluster de laboratório: `/api/erro` sempre responde HTTP 500 e
não deve receber tráfego de demonstração em produção.

```bash
chmod +x scripts/atividade-12-simular-incidente.sh
./scripts/atividade-12-simular-incidente.sh
```

O padrão gera uma resposta 500 por segundo durante 780 segundos para deixar
margem para o scrape, a janela de 5 minutos e `for: 10m`. Redirecione a saída
para guardar evidência, por exemplo:

```bash
./scripts/atividade-12-simular-incidente.sh | tee /tmp/atividade-12-incidente.log
```

Durante a execução, observe **Errors**, a série de erros por rota e o alerta
`TaxaDeErroAlta`. A rota existe permanentemente; a recuperação da simulação é
parar a geração de tráfego e observar a taxa cair e o alerta resolver. Não é
necessário reiniciar o Deployment para essa falha artificial.

O runbook operacional está em [runbook-5xx.md](./runbook-5xx.md). Registre
resultados reais em [postmortem-atividade-12.md](./postmortem-atividade-12.md);
não preencha impacto, horários ou alerta com valores não observados.
