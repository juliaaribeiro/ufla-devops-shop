# Atividade 5 — A stack completa

## Componentes

O `compose.yaml` sobe PostgreSQL, Redis, a API publicada no GHCR e Nginx. O
PostgreSQL usa o volume nomeado `dados-postgres`; somente o Nginx publica uma
porta (`80:80`). A senha fica no `.env`, criado localmente a partir de
`.env.example`, que não contém credenciais reais.

Imagem publicada: `ghcr.io/juliaaribeiro/ufla-shop:1.0.0`.

## Evidências

Preencha esta seção com a saída real após executar o roteiro do enunciado:

### `docker compose ps`

```text
NAME                       IMAGE                                   COMMAND                  SERVICE   CREATED          STATUS                    PORTS
ufla-devops-shop-api-1     ghcr.io/juliaaribeiro/ufla-shop:1.0.0   "uvicorn app:api --h…"   api       27 seconds ago   Up 19 seconds (healthy)   8000/tcp
ufla-devops-shop-banco-1   postgres:16-alpine                      "docker-entrypoint.s…"   banco     27 seconds ago   Up 25 seconds (healthy)   5432/tcp
ufla-devops-shop-cache-1   redis:7-alpine                          "docker-entrypoint.s…"   cache     27 seconds ago   Up 25 seconds (healthy)   6379/tcp
ufla-devops-shop-nginx-1   nginx:1.27-alpine                       "/docker-entrypoint.…"   nginx     26 seconds ago   Up 6 seconds (healthy)    0.0.0.0:80->80/tcp, [::]:80->80/tcp
```

### Persistência após `down` e `up`

```text
POST /api/produtos:
{"id":13,"nome":"Prova de persistencia","descricao":"","preco":9.9,"estoque":1,"criado_em":"2026-09-28T23:29:03.518023+00:00"}

docker compose down: containers e rede removidos; volume nomeado preservado.
docker compose up -d --wait: os quatro serviços ficaram healthy.

GET /api/busca?q=persistencia após o reinício:
{"termo":"persistencia","total":1,"resultados":[{"id":13,"nome":"Prova de persistencia","descricao":"","preco":9.9,"estoque":1,"criado_em":"2026-09-28T23:29:03.518023+00:00"}]}

curl -I http://localhost: HTTP/1.1 200 OK
GET /api/info: {"aplicacao":"ufla-devops-shop","versao":"1.0.0","banco":"postgresql","cache":"redis","instancia":"ca864a3d7546"}
```

### Pacote GHCR

Imagem publicada: `ghcr.io/juliaaribeiro/ufla-shop:1.0.0`.

Saída do push: digest `sha256:340a91803ed3e362cd0b19741d0da581a8dad19880af320ad5b11c1f43c3c15c`.

Link do pacote: https://github.com/users/juliaaribeiro/packages/container/package/ufla-shop

Pull anônimo validado após `docker logout ghcr.io`:

```text
1.0.0: Pulling from juliaaribeiro/ufla-shop
Digest: sha256:340a91803ed3e362cd0b19741d0da581a8dad19880af320ad5b11c1f43c3c15c
Status: Image is up to date for ghcr.io/juliaaribeiro/ufla-shop:1.0.0
```

O pacote está público e pode ser baixado sem autenticação.

## Ordem de inicialização

`depends_on` sem condição só inicia os containers na ordem configurada; isso não
significa que o PostgreSQL já aceita conexões. `condition: service_healthy`
espera o healthcheck do serviço passar antes de iniciar a API, evitando que ela
suba antes do banco e do Redis estarem prontos.
