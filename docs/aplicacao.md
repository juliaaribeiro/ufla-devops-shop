# A aplicação: `ufla-devops-shop`

Uma loja virtual mínima — catálogo, busca, carrinho e pedido — escrita para ser
**operada**, não para ser vendida. A complexidade do semestre está na esteira
(container, CI/CD, cluster, observabilidade, infraestrutura como código), não no
domínio do negócio. Por isso o código é curto e sem *framework* de ORM: dá para
ler tudo em meia hora.

```
app/
├── __init__.py    # expõe `api`  →  uvicorn app:api
├── __main__.py    # python -m app (atalho de desenvolvimento)
├── config.py      # variáveis de ambiente
├── banco.py       # PostgreSQL (psycopg) ou SQLite, escolhido pelo ambiente
├── cache.py       # Redis ou memória do processo, idem
└── principal.py   # a API FastAPI e as rotas
static/            # front estático: HTML, CSS e JS puros, servidos pela API em /
tests/             # pytest; roda sem nenhum serviço externo
requirements.txt      # dependências de EXECUÇÃO (só isto vai para a imagem)
requirements-dev.txt  # + pytest, cobertura, httpx2 e ruff (CI e desenvolvimento)
pyproject.toml        # configuração do ruff, do pytest e da cobertura
```

## Dois modos de execução

A aplicação decide sozinha como rodar, pela presença de duas variáveis:

| Variável       | Ausente                       | Presente                                  |
|----------------|-------------------------------|-------------------------------------------|
| `DATABASE_URL` | SQLite em arquivo (`loja.db`) | PostgreSQL, ex.: `postgresql://postgres:senha@banco:5432/loja` |
| `REDIS_URL`    | cache na memória do processo  | Redis, ex.: `redis://cache:6379/0`        |

**Modo autônomo** (nenhuma variável): sobe em qualquer lugar, sem serviço nenhum.
É assim que ela roda na Atividade 4 (um container sozinho) e na Atividade 9
(um Deployment no `kind`, ainda sem banco). Os dados ficam no arquivo SQLite e
morrem com o container — o que é, propositalmente, o problema que as semanas
seguintes resolvem.

**Modo completo** (as duas variáveis): PostgreSQL guarda produtos e pedidos,
Redis guarda a lista de produtos em cache (30 s) e os carrinhos (1 h). É a
configuração da Atividade 5 em diante.

Outras variáveis: `SQLITE_PATH` (caminho do arquivo no modo autônomo),
`CACHE_TTL` (segundos de cache da lista) e `PORT` (só para `python -m app`).

O esquema do banco (tabelas `produtos` e `pedidos`) é criado na subida, e um
catálogo inicial de 12 produtos é carregado se a tabela estiver vazia. Tudo
idempotente: subir de novo não duplica nada.

## Rotas

Rotas de **operação** — é com elas que Docker, Kubernetes e Prometheus conversam:

| Rota          | Para quê                                                                   |
|---------------|----------------------------------------------------------------------------|
| `GET /health` | *liveness*: "o processo está vivo?". Nunca toca em banco ou cache.          |
| `GET /ready`  | *readiness*: "posso receber tráfego?". `200` só se banco **e** cache respondem; `503` caso contrário. |
| `GET /api/info` | versão, modo do banco, modo do cache e **nome da instância** que respondeu (no Kubernetes, o nome do pod). |
| `GET /api/erro` | devolve `500` de propósito. Serve para simular um incidente na Semana 13. |
| `GET /docs`   | documentação interativa (OpenAPI), gerada pelo FastAPI.                    |

Rotas de **negócio**:

| Rota                                   | Para quê                                        |
|----------------------------------------|-------------------------------------------------|
| `GET /api/produtos`                    | lista o catálogo (passa pelo cache)              |
| `GET /api/produtos/{id}`               | um produto; `404` se não existe                  |
| `POST /api/produtos`                   | cria um produto (`nome`, `descricao`, `preco`, `estoque`) — `201` |
| `GET /api/busca?q=termo`               | busca por nome ou descrição, sem distinguir maiúsculas |
| `POST /api/carrinho`                   | cria um carrinho vazio — `201`                   |
| `GET /api/carrinho/{id}`               | consulta; `404` se não existe ou expirou         |
| `POST /api/carrinho/{id}/itens`        | adiciona (`produto_id`, `quantidade`); `409` se não há estoque |
| `POST /api/carrinho/{id}/finalizar`    | fecha o pedido e baixa o estoque, na mesma transação — `201` |
| `GET /api/pedidos`                     | pedidos fechados                                 |
| `GET /`                                | o front                                          |

## Rodar na sua máquina

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app:api --reload            # http://localhost:8000
```

Sem nada além disso a aplicação sobe em modo autônomo. Para experimentar o modo
completo sem instalar nada, suba as dependências em containers:

```bash
docker run -d --name banco -e POSTGRES_PASSWORD=senha -e POSTGRES_DB=loja -p 5432:5432 postgres:16-alpine
docker run -d --name cache -p 6379:6379 redis:7-alpine
export DATABASE_URL=postgresql://postgres:senha@localhost:5432/loja
export REDIS_URL=redis://localhost:6379/0
uvicorn app:api --reload
```

Ou instale os serviços no sistema (`apt install postgresql redis-server`,
`brew install postgresql@16 redis`) — é o caminho da Atividade 3, em que a
aplicação roda como processo gerenciado pelo `systemd`.

Testes, cobertura e *lint*, exatamente como o CI vai rodar:

```bash
ruff check .
pytest --cov=app --cov-report=term
```

Os testes rodam no modo autônomo, com um SQLite temporário: não precisam de
PostgreSQL nem de Redis. Isso é deliberado — um teste unitário que exige serviço
externo não é unitário.

## Encerramento limpo

O `uvicorn` trata `SIGTERM`: para de aceitar conexões, termina as requisições
em andamento e sai. Isso só funciona se ele for o **PID 1** do container — ou
seja, `CMD` na forma *exec* (`["uvicorn", "app:api", ...]`), nunca na forma
*shell*. A Atividade 4 mede o tempo do `docker stop`; com a forma certa é menos
de 1 segundo, com a forma errada são 10 segundos e um `SIGKILL`.

## Tamanho da imagem — números reais

Medidos em setembro de 2026, arquitetura `amd64`, tamanho descompactado (o que
`docker images` mostra em Linux):

| Imagem                                        | Tamanho |
|-----------------------------------------------|---------|
| `python:3.12-slim` (base, sem nada)           | 125 MB  |
| `python:3.12-slim` + `requirements.txt`       | 168 MB  |
| `python:3.12-slim` + deps, sem `pip` e caches | 155 MB  |
| `python:3.12-alpine` (base, sem nada)         | 60 MB   |
| `python:3.12-alpine` + `requirements.txt`     | 101 MB  |

Todas as dependências têm *wheels* para `musl`, então a base Alpine funciona sem
compilar nada. O que pesa nas dependências é o `psycopg[binary]`, que carrega a
`libpq` e o OpenSSL dentro do pacote (~25 MB) — o preço de não depender de
biblioteca do sistema.

## Como a aplicação atravessa o semestre

| Semana | O que ela ganha                                                        |
|--------|------------------------------------------------------------------------|
| 4      | roda como processo Linux: `systemd`, backup com `pg_dump`, Nginx à frente |
| 5      | vira imagem Docker (multi-stage, não-root, `HEALTHCHECK` em `/health`)   |
| 6      | a stack sobe com `docker compose`: `api`, `banco`, `cache`, `nginx`      |
| 7–8    | CI com `ruff` + `pytest`; CD publica a imagem no GHCR e faz *release*    |
| 9      | o pipeline barra CVE, segredo vazado e código ruim; gera SBOM            |
| 10–11  | Deployment, Service, Ingress, ConfigMap, Secret, probes em `/health` e `/ready`, HPA sob carga em `/api/produtos` |
| 12     | Helm chart e GitOps com ArgoCD                                           |
| 13     | métricas RED, painel, alerta; incidente simulado com `/api/erro`         |
| 14     | tudo isso descrito em Terraform                                          |

## Fork desatualizado?

Você fez o *fork* antes de a aplicação existir. `git pull` puxa **do seu fork**,
não daqui — então o código não chega sozinho. Traga-o assim:

```bash
git remote add upstream https://github.com/rdurelli/ufla-devops-shop.git   # uma vez só
git fetch upstream
git switch main
git merge upstream/main
git push origin main
```

Ou clique em **Sync fork → Update branch** na página do seu fork no GitHub e
depois `git pull`. Repita isso no início de **toda** atividade: o repositório da
turma ganha arquivos novos ao longo do semestre.
