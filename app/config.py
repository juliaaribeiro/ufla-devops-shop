"""Configuracao lida do ambiente.

Nada aqui e obrigatorio: sem variavel nenhuma a aplicacao sobe em modo
autonomo (SQLite em arquivo + cache em memoria). E assim que ela roda na
Atividade 4 (um container sozinho) e na Atividade 9 (um Deployment sem banco).

Variavel          Exemplo                                        Efeito
DATABASE_URL      postgresql://postgres:senha@banco:5432/loja    usa PostgreSQL
REDIS_URL         redis://cache:6379/0                           usa Redis
SQLITE_PATH       /dados/loja.db                                 caminho do SQLite (modo autonomo)
CACHE_TTL         30                                             segundos de cache da lista
PORT              8000                                           porta (so para ``python -m app``)
"""

import os
import socket

VERSAO = "1.0.0"

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
REDIS_URL = os.getenv("REDIS_URL", "").strip()
SQLITE_PATH = os.getenv("SQLITE_PATH", "loja.db")
CACHE_TTL = int(os.getenv("CACHE_TTL", "30"))

# Em Kubernetes o HOSTNAME e o nome do pod: util para ver qual replica respondeu.
INSTANCIA = os.getenv("HOSTNAME") or socket.gethostname()
