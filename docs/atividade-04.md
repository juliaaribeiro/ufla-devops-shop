# Atividade 4 — Containerizar a aplicação

## Imagem

A imagem foi construída em dois estágios com `python:3.12-alpine`. O estágio
final contém apenas o ambiente virtual com as dependências de execução, o código
da API e os arquivos estáticos. O processo roda como usuário não-root `app`.

O modo autônomo usa SQLite em `/data/loja.db` e cache em memória. O endpoint
`GET /health` verifica a vida da API sem depender de PostgreSQL ou Redis.

## Tamanho

| Etapa | Imagem | Tamanho |
|-------|--------|---------|
| Antes da otimização | `python:3.12-slim` + `requirements.txt` | 168 MB (referência medida em `docs/aplicacao.md`) |
| Depois da otimização | `ufla-shop:1.0` | 116 MB |

A imagem final ficou abaixo do limite de 150 MB. Saída real de `docker images
ufla-shop` após o build:

```text
REPOSITORY   TAG       IMAGE ID       CREATED              SIZE
ufla-shop    1.0       340a91803ed3   About a minute ago   116MB
```

## Verificações

- `GET /health` respondeu `{"status":"ok","versao":"1.0.0"}`.
- `docker inspect` reportou o estado `healthy`.
- `time docker stop ufla-shop-test-final` levou `0,847 s`, abaixo de 2 s.
- `CMD` usa a forma exec com `uvicorn` como processo PID 1 para receber `SIGTERM`.
