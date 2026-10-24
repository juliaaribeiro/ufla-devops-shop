# Atividade 10 — Kubernetes

## Arquitetura e decisões

- `Deployment/ufla-shop`: duas réplicas mínimas da API FastAPI (imagem
  `ghcr.io/juliaaribeiro/ufla-shop:1.0.0`, porta 8000), exposta internamente
  pelo Service `ufla-shop:80`.
- `StatefulSet/postgres`: uma instância PostgreSQL 16 com um PVC `ReadWriteOnce`
  de 1 GiB por ordinal, criado por `volumeClaimTemplates`. Os Services
  `postgres-headless` e `postgres` atendem à identidade estável do StatefulSet
  e às conexões da aplicação, respectivamente. O volume não é compartilhado
  entre instâncias independentes.
- `Deployment/cache`: uma instância Redis interna. A aplicação guarda carrinhos
  no cache; compartilhar Redis evita que carrinhos criados numa réplica da API
  desapareçam ao consultar outra. O cache é volátil e não é banco de dados.
- `ConfigMap/ufla-shop-config`: nome/host/porta do banco e configuração do
  cache. `Secret/postgres-credentials`: usuário e senha do PostgreSQL, criados
  localmente a partir de `.env`, nunca versionados.
- `Ingress/ufla-shop`: host `loja.local`; `/api` e `/` apontam para o Service da
  aplicação. A API realmente serve a página inicial e as rotas `/api`.
- `HorizontalPodAutoscaler/ufla-shop` (`autoscaling/v2`): 2 a 10 réplicas,
  CPU média alvo de 70% dos requests. Não há HPA para o PostgreSQL.

O PostgreSQL tem **uma única réplica e não oferece alta disponibilidade**. O
PVC protege os dados contra a recriação do Pod, não contra perda do cluster,
falha do nó/volume ou corrupção. O Redis também tem uma réplica e não possui
persistência configurada: carrinhos são dados temporários.

Todos os Pods definidos aqui têm requests e limits; portanto, a classe QoS
esperada é **Burstable** (requests menores que limits). Os requests foram
dimensionados para o ambiente didático/local: API 100m CPU/128 MiB, PostgreSQL
100m/256 MiB e Redis 50m/64 MiB. Os limits (API e PostgreSQL 500m/512 MiB;
Redis 250m/256 MiB) limitam o consumo em um cluster kind pequeno. Ajuste-os
mediante medição no ambiente real.

## Pré-requisitos e kind

São necessários Docker funcional, `kind`, `kubectl`, `curl` e `openssl`.
Para demonstrar autoscaling, instale também `metrics-server`; para Ingress, é
necessário um Ingress Controller. O recurso Ingress sozinho não implementa um
controlador. Para executar a carga, instale Go.

O arquivo `k8s/kind-config.yaml` cria um control-plane e dois workers, marca o
control-plane para o controller de Ingress e publica as portas locais 80/443.
As portas devem estar livres no host. Mapeamentos de porta são definidos na
criação do cluster: um cluster já existente criado sem eles não os recebe ao
reaplicar o YAML. Não apague um cluster que contenha dados; use um cluster
novo ou, para teste provisório, o `kubectl port-forward` abaixo.

```bash
kind create cluster --name ufla-shop --config k8s/kind-config.yaml
kubectl cluster-info
kubectl get nodes -o wide
kubectl get storageclass
```

O PVC precisa de um provisioner dinâmico. Primeiro verifique se há uma classe
padrão. Se não houver, instale o provisioner local do kind e marque `local-path`
como padrão. O volume resultante reside em um nó local do cluster e não é uma
solução de backup/alta disponibilidade:

```bash
kubectl get storageclass
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.37/deploy/local-path-storage.yaml
kubectl rollout status deployment/local-path-provisioner -n local-path-storage --timeout=180s
kubectl patch storageclass local-path --type=merge \
  -p='{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
kubectl get storageclass
```

Se o cluster já tiver uma classe padrão funcional, não instale/defina outra sem
necessidade. Não avance se não houver classe padrão, ou se o PVC ficar
`Pending`.

### Ingress Controller

Instale um controller compatível com a classe `nginx`. Para um cluster kind
local, o manifesto oficial do provider kind configura o controller para as
portas 80/443 e para o nó marcado acima:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.15.1/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=Ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=180s
kubectl get ingressclass
```

Confirme que a classe `nginx` existe antes de aplicar `k8s/ingress.yaml`. A versão
do controller deve ser compatível com a versão do Kubernetes do cluster.

### Metrics Server para HPA

O metrics-server não é instalado pelo kind por padrão. Instale-o segundo a
documentação oficial para a versão do seu cluster. Em kind, se a coleta falhar
por validação TLS do kubelet, essa configuração é aceitável somente no
laboratório local; **não** use `--kubelet-insecure-tls` em produção. Verifique a
API de métricas antes de confiar no HPA:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.9.0/components.yaml
kubectl rollout status deployment/metrics-server -n kube-system --timeout=180s
kubectl get deployment metrics-server -n kube-system
kubectl get apiservice v1beta1.metrics.k8s.io
kubectl top nodes
```

Os comandos devem retornar Deployment disponível, API `Available=True` e
métricas. Sem isso, o HPA aparece como `unknown` e não escala. Se `kubectl top`
falhar especificamente por certificado TLS do kubelet no kind, aplique este
ajuste apenas no cluster didático local e repita a validação:

```bash
kubectl patch deployment metrics-server -n kube-system --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl rollout status deployment/metrics-server -n kube-system --timeout=180s
kubectl top nodes
```

## Credenciais, instalação e execução

O `.env` é ignorado pelo Git. Gere uma senha local aleatória em hexadecimal
(caracteres seguros para a URI PostgreSQL), sem exibi-la nem adicioná-la ao
repositório. A senha no Secret é codificada em Base64 pelo Kubernetes; **Base64
não é criptografia**. Proteja o cluster, o acesso à API e o arquivo `.env`.
O bloco abaixo cria `.env` somente se ainda não existir; se ele já existe,
preserve-o e confira localmente se a senha não é o valor de exemplo.

```bash
if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
fi
kubectl create secret generic postgres-credentials \
  --from-literal=POSTGRES_USER="$(sed -n 's/^POSTGRES_USER=//p' .env)" \
  --from-literal=POSTGRES_PASSWORD="$(sed -n 's/^POSTGRES_PASSWORD=//p' .env)" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f k8s/app-config.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/cache.yaml
kubectl wait --for=condition=Ready pod/postgres-0 --timeout=180s
kubectl wait --for=condition=available deployment/cache --timeout=180s
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml
kubectl wait --for=condition=available deployment/ufla-shop --timeout=180s
```

Não aplique `kubectl apply -f k8s/` indiscriminadamente: `k8s/debug/` contém
manifests intencionalmente inválidos para exercícios. A senha não deve ser
incluída em comandos registrados no histórico, logs ou capturas de tela. O
Secret também pode ser criado por um gerenciador de segredos da organização.

## Probes e comportamento esperado

- API `startupProbe`: `GET /health` a cada 5 s, até 30 falhas (150 s). Permite
  inicialização lenta sem que a liveness reinicie prematuramente o processo.
- API `readinessProbe`: `GET /ready` a cada 5 s. Essa rota verifica PostgreSQL
  e Redis e retorna 503 se algum deles não responder; a réplica não recebe
  tráfego enquanto não estiver pronta.
- API `livenessProbe`: `GET /health` a cada 10 s. `/health` verifica somente o
  processo, sem depender de banco/cache, evitando reinícios em cascata durante
  indisponibilidade externa.
- PostgreSQL: `pg_isready` local em startup/readiness/liveness. Redis:
  `redis-cli ping`. Os tempos permitem a inicialização inicial e detectam
  falhas sem consultas externas.

Readiness é deliberadamente dependente de serviços externos; liveness não é.
Probes e recursos existem também para os containers PostgreSQL e Redis.

## Validação funcional e evidências

Confira recursos, seletores, endpoints, PVC, estado dos Pods, QoS e probes:

```bash
kubectl get configmap,secret,deploy,statefulset,service,ingress,hpa,pods,pvc -o wide
kubectl get pods -o custom-columns='NAME:.metadata.name,READY:.status.containerStatuses[*].ready,QOS:.status.qosClass,NODE:.spec.nodeName'
kubectl get endpoints ufla-shop postgres cache
kubectl describe deployment ufla-shop
kubectl describe statefulset postgres
kubectl describe hpa ufla-shop
kubectl get pvc
```

Teste a rota real pelo Ingress (o `--resolve` dispensa editar `hosts`):

```bash
curl --fail --show-error --resolve loja.local:80:127.0.0.1 http://loja.local/health
curl --fail --show-error --resolve loja.local:80:127.0.0.1 http://loja.local/api/produtos
curl --fail --show-error --resolve loja.local:80:127.0.0.1 'http://loja.local/api/busca?q=caneca'
```

Para abrir no navegador, mapeie `127.0.0.1 loja.local` no arquivo `hosts` do
sistema host. Se as portas 80/443 não estiverem mapeadas no cluster, use
temporariamente `kubectl port-forward service/ufla-shop 8080:80` e acesse
`http://127.0.0.1:8080/health` e `/api/produtos`.

### Persistência sem remover o volume

Para demonstrar que os dados sobrevivem à substituição do Pod, crie um produto
de teste pela API e anote o `id` retornado. Use valores de teste únicos; essa
operação acrescenta um registro e não o remove:

```bash
curl --fail --show-error --resolve loja.local:80:127.0.0.1 \
  -H 'Content-Type: application/json' \
  -d '{"nome":"Produto de teste persistencia","descricao":"Atividade 10","preco":1.23,"estoque":1}' \
  http://loja.local/api/produtos
```

Confira o registro em `/api/produtos/{id}`, reinicie somente o StatefulSet e
confira o mesmo ID novamente após o Pod voltar. Troque `ID_TESTE` pelo ID retornado.
O PVC permanece ligado ao ordinal `postgres-0`; **não delete o PVC**:

```bash
curl --fail --show-error --resolve loja.local:80:127.0.0.1 \
  http://loja.local/api/produtos/ID_TESTE
kubectl get pvc
kubectl rollout restart statefulset/postgres
kubectl rollout status statefulset/postgres --timeout=180s
kubectl get pod postgres-0 -o wide
curl --fail --show-error --resolve loja.local:80:127.0.0.1 \
  http://loja.local/api/produtos/ID_TESTE
kubectl get pvc
```

Essa validação demonstra persistência após recriação do Pod, não alta
disponibilidade nem recuperação contra perda do volume/cluster.

## HPA e carga com hey

Além de metrics-server disponível, o Deployment precisa manter `requests.cpu`
(100m por réplica); o alvo de 70% é calculado em relação a esse request. A
instalação do HPA não gera carga automaticamente. Instale o `hey` com Go e
rode as capturas em terminais separados:

```bash
go install github.com/rakyll/hey@latest
export PATH="$PATH:$(go env GOPATH)/bin"
hey -h
```

Terminal 1 — registrar réplicas a cada 5 segundos, antes e durante a carga:

```bash
while true; do
  date -Is
  kubectl get deployment ufla-shop -o custom-columns='DESIRED:.spec.replicas,READY:.status.readyReplicas,AVAILABLE:.status.availableReplicas'
  kubectl get hpa ufla-shop
  sleep 5
done | tee replicas-hpa.log
```

Terminal 2 — registrar estado antes, gerar 60 segundos de carga concorrente 50
no endpoint real de busca e registrar estado depois:

```bash
kubectl get deployment ufla-shop
kubectl top pods -l app=ufla-shop
hey -z 60s -c 50 'http://loja.local/api/busca?q=caneca'
kubectl get deployment ufla-shop
kubectl get hpa ufla-shop
kubectl top pods -l app=ufla-shop
```

Espere até cinco minutos após o teste para observar redução de réplicas; a
janela de estabilização de scale-down configurada é 60 s, além dos intervalos
de coleta do HPA. Registre os valores observados antes, durante e depois — não
presuma que uma carga de 60 s necessariamente escalará: a decisão depende da
CPU medida, da cadência de coleta e do tempo de inicialização. `kubectl top`,
`kubectl describe hpa ufla-shop` e os eventos explicam ausência de escala.
Interrompa a captura do Terminal 1 com `Ctrl+C` depois de registrar o período
posterior ao teste.

## Diagnóstico

Comece por `kubectl get`, depois `kubectl describe` e `kubectl logs`:

```bash
kubectl get pods,pvc,events --sort-by=.metadata.creationTimestamp
kubectl describe pod <pod>
kubectl logs <pod> --all-containers
kubectl logs <pod> --all-containers --previous
kubectl describe hpa ufla-shop
kubectl get apiservice v1beta1.metrics.k8s.io
```

- PVC `Pending`: confirme StorageClass/provisioner (`kubectl get storageclass`)
  e eventos do PVC.
- API não `Ready`: confira Secret/ConfigMap, `kubectl logs` e estado de
  `postgres-0` e `cache`; `/ready` deliberadamente não recebe tráfego se banco
  ou cache estiverem indisponíveis.
- Ingress sem endereço/rota: confira o controller, `IngressClass nginx`, portas
  80/443, `kubectl describe ingress ufla-shop` e DNS/`hosts`.
- HPA sem métricas: confira requests, metrics-server, `kubectl top pods` e
  `kubectl describe hpa`.
- Persistência: verifique que o PVC existente está Bound e associado ao Pod.
  Não apague PVCs ou volumes durante esse diagnóstico.

O workflow da Atividade 09 também cria um cluster efêmero em runner Linux e
registra evidências do Deployment. Agora ele cria credenciais descartáveis e
aplica ConfigMap, PostgreSQL e Redis antes da API; não instala controller de
Ingress nem metrics-server.
