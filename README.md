# Checkpoint 2 — GitOps com Helm e ArgoCD

## Objetivo

Empacotar e implantar a aplicação FastAPI por GitOps. O Git contém o estado
desejado; o Argo CD busca esse estado e reconcilia continuamente o cluster.
Alterações são feitas por commit. O rollback é feito com `git revert`, não com
rollback manual do Helm.

## Estrutura

- `helm/checkpoint2-app/Chart.yaml`: metadados do chart.
- `helm/checkpoint2-app/values.yaml`: valores padrão.
- `helm/checkpoint2-app/values-staging.yaml`: parâmetros de staging.
- `helm/checkpoint2-app/values-prod.yaml`: parâmetros de produção.
- `helm/checkpoint2-app/templates/`: Deployment, Service e SealedSecret.
- `argocd/`: Applications dos dois ambientes.

O chart é o pacote, os values são parâmetros e os templates são moldes. Cada
Application cria uma release Helm gerenciada pelo Argo CD. Não há manifests
soltos de Deployment ou Service por ambiente.

## Diferenças entre staging e produção

Staging usa uma réplica e limites menores para validar alterações com menor
consumo de recursos. Produção usa duas réplicas para manter mais capacidade
disponível e limites maiores. As mensagens `APP_MESSAGE` também diferenciam
visivelmente os ambientes durante a validação.

Esses valores são pontos de partida para a atividade; devem ser ajustados se
houver requisitos de capacidade ou quotas do cluster.

## GitOps e Argo CD

As Applications apontam para a branch `checkpoint-02` e para o chart
`helm/checkpoint2-app`. Cada uma seleciona o values file do seu ambiente.
`automated` habilita sincronização automática, `prune: true` remove recursos
retirados do Git e `selfHeal: true` corrige alterações feitas diretamente no
cluster.

O modelo é pull: o agente do Argo CD dentro do cluster busca o estado
declarativo no Git e reconcilia o cluster. Drift é a diferença entre o estado
real do cluster e o estado versionado.

## Segredo com Sealed Secrets

Nunca grave um Secret em texto claro no Git. Base64 não é criptografia. O
chart recebe apenas o ciphertext produzido por `kubeseal`; a chave privada de
descriptografia permanece no cluster.

**A implantação ainda não está pronta para sincronizar:** os dois values files
contêm `sealedSecret.encryptedApiToken` vazio. Não foi fornecido o valor real
do `API_TOKEN` nem confirmado um controller/certificado Sealed Secrets. Não
substitua o campo por um texto arbitrário. O template falha intencionalmente
na renderização enquanto o ciphertext estiver ausente.

Verifique se o CRD e o controller estão instalados:

```bash
kubectl get crd sealedsecrets.bitnami.com
kubectl get pods -A | grep sealed-secrets
```

Se o controller não estiver instalado, pare e combine a instalação com quem
administra o cluster. Não instale componentes no cluster de produção sem
autorização.

Com o controller disponível e `kubeseal` configurado para acessá-lo, gere um
ciphertext para cada namespace. O valor será lido sem eco e enviado pelo pipe;
não o escreva em arquivo nem o inclua em comandos salvos no histórico:

```bash
read -rsp "API_TOKEN de staging: " API_TOKEN
printf '\n'
printf '%s' "$API_TOKEN" | kubeseal --raw --from-file=/dev/stdin \
  --namespace devops-staging \
  --name checkpoint2-app-secret \
  --scope namespace-wide
unset API_TOKEN
```

Repita para produção, trocando o namespace para `devops-prod`. Copie cada
saída ciphertext para `sealedSecret.encryptedApiToken` no values file
correspondente. O escopo `namespace-wide` ainda vincula o ciphertext ao
namespace. Não copie nem versione um Secret Kubernetes em texto claro.

## Validar o chart

Depois de preencher os ciphertexts:

```bash
helm lint helm/checkpoint2-app
helm template checkpoint2-staging helm/checkpoint2-app \
  --namespace devops-staging \
  --values helm/checkpoint2-app/values-staging.yaml
helm template checkpoint2-prod helm/checkpoint2-app \
  --namespace devops-prod \
  --values helm/checkpoint2-app/values-prod.yaml
```

O Argo CD usa Helm para renderizar o chart e é o responsável por aplicar os
recursos nos ambientes.

Não execute `helm upgrade` nos namespaces gerenciados pelo Argo CD: isso
contornaria o Git como fonte da verdade. Se a disciplina exigir demonstrar
`helm upgrade --atomic --wait`, faça isso somente em um cluster descartável,
isolado dos ambientes GitOps. O rollback dos ambientes GitOps é sempre feito
com `git revert`.

## Publicação e Applications

Antes de publicar, confirme que a imagem referenciada existe e é acessível ao
cluster. O workflow do repositório publica
`ghcr.io/juliaaribeiro/docker-pratico` e prevê a tag `1.0`; se o pacote for
privado, configure acesso de pull no cluster sem versionar credenciais em
texto claro.

As Applications devem ser aplicadas somente depois que a branch
`checkpoint-02` estiver publicada e os ciphertexts estiverem preenchidos:

```bash
kubectl apply -f argocd/checkpoint2-staging.yaml
kubectl apply -f argocd/checkpoint2-prod.yaml
argocd app wait checkpoint2-staging --sync --health --timeout 300
argocd app wait checkpoint2-prod --sync --health --timeout 300
```

## Evidências

- Sincronização: `argocd app get checkpoint2-staging` e
  `argocd app get checkpoint2-prod`.
- Applications: `argocd app list`.
- `prune` e `selfHeal`: inspecione `spec.syncPolicy.automated` nos dois
  recursos Application.
- Sealed Secrets: verifique a presença de `SealedSecret` no Git e no cluster.
  Não use `kubectl get secret -o yaml`, pois isso pode exibir dados do Secret.
- Self-heal e rollback: registre o estado antes e depois conforme o roteiro
  do checkpoint, mantendo os comandos e saídas como evidência.

## Prova de self-heal

**Aviso:** este comando altera manualmente o Deployment de staging no cluster.
Execute apenas com autorização, no contexto correto, e capture a evidência
imediatamente: o Argo CD pode corrigir o drift em poucos segundos.

```bash
kubectl scale deployment/checkpoint2-staging-checkpoint2-app \
  -n devops-staging --replicas=3
argocd app get checkpoint2-staging
argocd app diff checkpoint2-staging
kubectl get deployment checkpoint2-staging-checkpoint2-app \
  -n devops-staging -o jsonpath='{.spec.replicas}{"\n"}'
```

Registre a diferença entre o valor manual (`3`) e o desejado no Git (`1`), e
depois o retorno para `1`. Também registre a Application como `Synced` após a
reconciliação:

```bash
argocd app wait checkpoint2-staging --sync --health --timeout 300
argocd app get checkpoint2-staging
```

## Rollback via `git revert`

**Aviso:** a alteração commitada será sincronizada automaticamente em staging
e produção, pois ambas apontam para `checkpoint-02`. Combine a mudança com a
equipe antes de fazê-la.

Altere, por exemplo, `appMessage` em `values-prod.yaml`; depois:

```bash
git add helm/checkpoint2-app/values-prod.yaml
git commit -m "Change production app message"
git push
argocd app wait checkpoint2-prod --sync --health --timeout 300
```

Registre o estado após a sincronização. Reverta o commit e publique a
reversão:

```bash
git revert <hash-do-commit-de-alteracao>
git push
argocd app wait checkpoint2-prod --sync --health --timeout 300
argocd app get checkpoint2-prod
```

Registre o retorno ao valor anterior definido no Git.
