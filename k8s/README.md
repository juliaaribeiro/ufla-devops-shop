# Kubernetes para o ufla-devops-shop

## Resumo da estrutura encontrada antes da implementação

- Porta da aplicação: `8000`
- Comando de inicialização: `uvicorn app:api --host 0.0.0.0 --port 8000`
- Nome da imagem: `ghcr.io/juliaaribeiro/ufla-shop`
- Última tag/version disponível: `1.0.0`
- O pacote no GHCR é público, então o `kind` consegue fazer pull diretamente sem carregar a imagem localmente.
- No modo autônomo, a aplicação roda sem PostgreSQL/Redis usando SQLite em arquivo; por isso ela funciona em um `Deployment` simples no `kind` sem nenhum banco externo.

## Criar o cluster kind

```bash
kind create cluster --name ufla-shop --config k8s/kind-config.yaml
kubectl get nodes -o wide
```

O resultado esperado é um cluster com exatamente:

- 1 control-plane
- 2 workers

## Executar as evidências no GitHub Actions

Se Docker Desktop no computador não conseguir iniciar os nós kind, o workflow
**Atividade 09 - evidências kind** executa esta prática em um runner Ubuntu
hospedado pelo GitHub. Ele é iniciado ao fazer `push` na branch `atividade-09`
(ou manualmente pelo GitHub Actions quando o workflow estiver disponível).

Após a execução, baixe o artefato `atividade-09-kind-evidencias-<run-id>`. Ele
contém a listagem dos nós, os Pods e seus nós de agendamento, o tempo até a
réplica substituta ficar Ready, as evidências de rollout/undo, as saídas de
diagnóstico e os logs exportados do kind. O workflow remove o cluster temporário
ao final, inclusive quando uma etapa falha.

Para disparar pelo push da branch:

```bash
git add .github/workflows/atividade-09-kind.yml scripts/atividade-09-kind-ci.sh k8s
git commit -m "feat: evidencias da atividade 09 com kind"
git push -u origin atividade-09
```

Depois acompanhe a execução em **Actions** no GitHub e baixe o artefato gerado.
O repositório precisa ter GitHub Actions habilitado.

As evidências são de uma execução em CI, não do computador local. Confirme com
o professor que esse formato é aceito para a entrega. O workflow não publica
imagens nem altera o cluster local; para o rollout, constrói a imagem do commit
executado e carrega-a apenas no cluster temporário.

## Implantar a aplicação

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl get deployment,service,pods -l app=ufla-shop -o wide
kubectl wait --for=condition=available deployment/ufla-shop --timeout=180s
```

## Verificações de funcionamento

```bash
kubectl get pods -o wide
kubectl get endpoints ufla-shop
kubectl port-forward service/ufla-shop 8080:80
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
```

## Reconciliation: apagar um Pod

```bash
kubectl get pods -l app=ufla-shop -o wide
POD_NAME=$(kubectl get pod -l app=ufla-shop -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod "$POD_NAME"
kubectl get pods -l app=ufla-shop -o wide --watch
```

O Deployment cria um novo Pod em seguida. O tempo de recriação pode ser medido com `date +%s` antes e depois do `delete`.

## Escalar o Deployment

```bash
kubectl scale deployment/ufla-shop --replicas=6
kubectl get pods -o wide
kubectl describe nodes
```

Observe em quais nós o scheduler aloca os Pods.

## Rollout e rollback

```bash
kubectl rollout history deployment/ufla-shop
kubectl set image deployment/ufla-shop ufla-shop=ghcr.io/juliaaribeiro/ufla-shop:sha-<commit-sha>
kubectl rollout status deployment/ufla-shop
kubectl rollout undo deployment/ufla-shop
kubectl rollout status deployment/ufla-shop
```

Use uma tag imutável, como `1.0.0` ou `sha-<commit-sha>`, conforme publicada no GHCR. Não use `latest`.

## Diagnóstico de falhas do Deployment

O roteiro de aula enfatiza `get -> describe -> logs`.

### 1) Imagem inexistente

```bash
kubectl apply -f k8s/debug/invalid-image.yaml
kubectl get pods
kubectl describe pod -l app=ufla-shop-falha-imagem
kubectl logs -l app=ufla-shop-falha-imagem --previous
```

Status esperado: `ImagePullBackOff` ou `ErrImagePull`.

Correção:

```bash
kubectl delete -f k8s/debug/invalid-image.yaml
kubectl apply -f k8s/deployment.yaml
```

### 2) Comando inválido

```bash
kubectl apply -f k8s/debug/invalid-command.yaml
kubectl get pods
kubectl describe pod -l app=ufla-shop-falha-comando
kubectl logs -l app=ufla-shop-falha-comando --previous
```

Status esperado: `CrashLoopBackOff`.

Correção:

```bash
kubectl delete -f k8s/debug/invalid-command.yaml
kubectl apply -f k8s/deployment.yaml
```

### 3) Selector que não casa

```bash
kubectl apply -f k8s/debug/wrong-selector.yaml
```

Status esperado: o próprio `kubectl apply` retorna erro de validação porque
`spec.selector.matchLabels` não corresponde aos labels do template. O API server
rejeita o Deployment; portanto, não há Pod para inspecionar com `describe` ou
`logs`.

Correção:

```bash
kubectl apply -f k8s/deployment.yaml
```

## Arquivos versionados

- `k8s/kind-config.yaml`: cluster de 3 nós
- `k8s/deployment.yaml`: `Deployment` com 3 réplicas e probe HTTP
- `k8s/service.yaml`: `Service` do tipo `ClusterIP`
- `k8s/debug/*.yaml`: cenários de falha para exercício de diagnóstico

## Observações finais

Este repositório já expõe a aplicação no port `8000`, usa `uvicorn` e já publica a imagem imutável em `ghcr.io/juliaaribeiro/ufla-shop:1.0.0`. O `kind` consegue puxar a imagem diretamente do GHCR, então não é necessário qualquer carregamento local adicional da imagem.
