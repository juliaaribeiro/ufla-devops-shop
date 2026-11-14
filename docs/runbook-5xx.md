# Runbook — TaxaDeErroAlta

## Condição

O alerta `TaxaDeErroAlta` dispara quando a proporção de respostas HTTP 5xx
ultrapassa 2% durante 10 minutos. O alerta mede o sintoma do serviço; use as
métricas, logs e recursos Kubernetes para investigar a causa.

## Triagem

1. Abra o dashboard **UFLA DevOps Shop — Observabilidade** e confirme tráfego,
   percentual 5xx, p95 e saturação de CPU.
2. No Prometheus, valide a proporção:

   ```promql
   sum(rate(http_requests_total{status=~"5.."}[5m]))
   /
   sum(rate(http_requests_total[5m]))
   ```

3. Identifique as rotas que mais falham:

   ```promql
   sum by (route, status) (rate(http_requests_total{status=~"5.."}[5m]))
   ```

4. Verifique pods e logs no namespace afetado:

   ```bash
   kubectl get pods -n <namespace> -o wide
   kubectl logs -n <namespace> deploy/<deployment> --since=15m
   kubectl describe pod -n <namespace> <pod>
   ```

5. Verifique recursos e eventos:

   ```bash
   kubectl top pods -n <namespace>
   kubectl top nodes
   kubectl get events -n <namespace> --sort-by=.lastTimestamp
   ```

6. Compare erros por rota com logs e eventos. Verifique também dependências
   (PostgreSQL e Redis), configuração e alterações recentes; não conclua causa
   apenas pela correlação com CPU.
7. Faça rollback somente se houver uma alteração recente relacionada e um
   artefato conhecido como estável. Reinicie um Deployment apenas diante de
   evidência de falha recuperável no processo; restart não corrige dependência
   indisponível nem falha de aplicação.
8. Confirme a recuperação observando a queda da taxa 5xx, o retorno das rotas
   afetadas e a resolução do alerta após as janelas de `rate` e `for`.
9. Registre horário, namespace, rota, impacto medido e ações para o postmortem.

## Acesso

- Dashboard: `http://localhost:3000` (via port-forward de
  `svc/prometheus-grafana` no namespace `monitoring`).
- Prometheus: `http://localhost:9090` (via port-forward de
  `svc/prometheus-kube-prometheus-prometheus`).
- Para a simulação didática, use somente um cluster de laboratório; a rota
  existente `/api/erro` sempre responde 500.
