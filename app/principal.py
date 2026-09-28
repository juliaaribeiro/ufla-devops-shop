"""A API HTTP do ufla-devops-shop.

Rotas de operacao (usadas por Docker, Kubernetes e Prometheus):
    GET /health   vivo?  --- nao toca em dependencia nenhuma (liveness)
    GET /ready    pronto? --- confere banco e cache; 503 se algum falhar (readiness)
    GET /api/info versao, modo do banco/cache e nome da instancia que respondeu

Rotas de negocio:
    GET  /api/produtos               lista (com cache)
    GET  /api/produtos/{id}          um produto
    POST /api/produtos               cria um produto
    GET  /api/busca?q=termo          busca por nome ou descricao
    POST /api/carrinho               cria um carrinho
    GET  /api/carrinho/{id}          consulta o carrinho
    POST /api/carrinho/{id}/itens    adiciona um item
    POST /api/carrinho/{id}/finalizar fecha o pedido e baixa o estoque
    GET  /api/pedidos                pedidos fechados
    GET  /api/erro                   devolve 500 de proposito (para simular incidente)

O front estatico e servido em ``/`` e ``/static/``.
"""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config
from app.banco import Banco, BancoIndisponivel, EstoqueInsuficiente
from app.cache import Cache, CacheIndisponivel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("loja")

RAIZ = Path(__file__).resolve().parent.parent
ESTATICO = RAIZ / "static"

banco = Banco(config.DATABASE_URL, config.SQLITE_PATH)
cache = Cache(config.REDIS_URL)

CHAVE_PRODUTOS = "produtos:todos"
TTL_CARRINHO = 3600


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    log.info("ufla-devops-shop %s subindo (banco=%s, cache=%s, instancia=%s)",
             config.VERSAO, banco.modo, cache.modo, config.INSTANCIA)
    try:
        banco.garantir_esquema()
    except BancoIndisponivel as exc:
        # Nao derruba o processo: o /ready reporta, e a primeira requisicao tenta de novo.
        log.warning("banco indisponivel na subida (%s); seguirei tentando", exc)
    yield
    log.info("ufla-devops-shop encerrando")


api = FastAPI(
    title="ufla-devops-shop",
    version=config.VERSAO,
    description="Loja didática da disciplina DevOps na Prática (DCC/UFLA).",
    lifespan=ciclo_de_vida,
)


# ------------------------------------------------------------------ modelos
class ProdutoEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    descricao: str = Field(default="", max_length=500)
    preco: float = Field(gt=0)
    estoque: int = Field(default=0, ge=0)


class ItemEntrada(BaseModel):
    produto_id: int = Field(ge=1)
    quantidade: int = Field(default=1, ge=1, le=99)


# --------------------------------------------------------- tratamento de erro
@api.exception_handler(BancoIndisponivel)
async def _banco_fora(_: Request, exc: BancoIndisponivel) -> JSONResponse:
    log.error("banco indisponivel: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "banco de dados indisponível"})


@api.exception_handler(CacheIndisponivel)
async def _cache_fora(_: Request, exc: CacheIndisponivel) -> JSONResponse:
    log.error("cache indisponivel: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "cache indisponível"})


# ------------------------------------------------------------------ operacao
@api.get("/health", tags=["operação"])
def health() -> dict[str, str]:
    """Liveness: responde se o processo esta de pe. Nunca consulta dependencias."""
    return {"status": "ok", "versao": config.VERSAO}


@api.get("/ready", tags=["operação"])
def ready() -> JSONResponse:
    """Readiness: so e 200 quando banco e cache respondem."""
    estado = {
        "banco": "ok" if banco.ping() else "falha",
        "cache": "ok" if cache.ping() else "falha",
    }
    pronto = all(v == "ok" for v in estado.values())
    return JSONResponse(status_code=200 if pronto else 503,
                        content={"status": "ok" if pronto else "indisponível", **estado})


@api.get("/api/info", tags=["operação"])
def info() -> dict[str, str]:
    return {
        "aplicacao": "ufla-devops-shop",
        "versao": config.VERSAO,
        "banco": banco.modo,
        "cache": cache.modo,
        "instancia": config.INSTANCIA,
    }


@api.get("/api/erro", tags=["operação"])
def erro_proposital() -> None:
    """Sempre falha com 500. Serve para gerar 5xx num incidente simulado."""
    log.error("rota /api/erro chamada: falha proposital")
    raise HTTPException(status_code=500, detail="falha proposital para simular incidente")


# ------------------------------------------------------------------ produtos
@api.get("/api/produtos", tags=["produtos"])
def listar_produtos() -> list[dict[str, Any]]:
    try:
        em_cache = cache.obter(CHAVE_PRODUTOS)
    except CacheIndisponivel as exc:
        log.warning("cache fora, lendo do banco: %s", exc)
        em_cache = None
    if em_cache:
        return json.loads(em_cache)
    produtos = banco.listar_produtos()
    try:
        cache.guardar(CHAVE_PRODUTOS, json.dumps(produtos), config.CACHE_TTL)
    except CacheIndisponivel:
        pass
    return produtos


@api.get("/api/produtos/{produto_id}", tags=["produtos"])
def obter_produto(produto_id: int) -> dict[str, Any]:
    produto = banco.obter_produto(produto_id)
    if produto is None:
        raise HTTPException(status_code=404, detail="produto não encontrado")
    return produto


@api.post("/api/produtos", status_code=201, tags=["produtos"])
def criar_produto(entrada: ProdutoEntrada) -> dict[str, Any]:
    produto = banco.criar_produto(entrada.nome, entrada.descricao, entrada.preco, entrada.estoque)
    try:
        cache.apagar(CHAVE_PRODUTOS)
    except CacheIndisponivel:
        pass
    return produto


@api.get("/api/busca", tags=["produtos"])
def buscar(q: str = Query(min_length=1, max_length=60)) -> dict[str, Any]:
    resultados = banco.buscar_produtos(q)
    return {"termo": q, "total": len(resultados), "resultados": resultados}


# ------------------------------------------------------------------ carrinho
def _chave_carrinho(carrinho_id: str) -> str:
    return f"carrinho:{carrinho_id}"


def _carregar_carrinho(carrinho_id: str) -> dict[str, Any]:
    bruto = cache.obter(_chave_carrinho(carrinho_id))
    if bruto is None:
        raise HTTPException(status_code=404, detail="carrinho não encontrado ou expirado")
    return json.loads(bruto)


def _salvar_carrinho(carrinho: dict[str, Any]) -> dict[str, Any]:
    carrinho["total"] = round(sum(i["preco"] * i["quantidade"] for i in carrinho["itens"]), 2)
    cache.guardar(_chave_carrinho(carrinho["id"]), json.dumps(carrinho), TTL_CARRINHO)
    return carrinho


@api.post("/api/carrinho", status_code=201, tags=["carrinho"])
def criar_carrinho() -> dict[str, Any]:
    return _salvar_carrinho({"id": uuid.uuid4().hex[:12], "itens": []})


@api.get("/api/carrinho/{carrinho_id}", tags=["carrinho"])
def obter_carrinho(carrinho_id: str) -> dict[str, Any]:
    return _carregar_carrinho(carrinho_id)


@api.post("/api/carrinho/{carrinho_id}/itens", tags=["carrinho"])
def adicionar_item(carrinho_id: str, item: ItemEntrada) -> dict[str, Any]:
    carrinho = _carregar_carrinho(carrinho_id)
    produto = banco.obter_produto(item.produto_id)
    if produto is None:
        raise HTTPException(status_code=404, detail="produto não encontrado")
    existente = next((i for i in carrinho["itens"] if i["produto_id"] == item.produto_id), None)
    quantidade = item.quantidade + (existente["quantidade"] if existente else 0)
    if quantidade > produto["estoque"]:
        raise HTTPException(status_code=409,
                            detail=f"estoque insuficiente: restam {produto['estoque']}")
    if existente:
        existente["quantidade"] = quantidade
    else:
        carrinho["itens"].append({
            "produto_id": produto["id"],
            "nome": produto["nome"],
            "preco": produto["preco"],
            "quantidade": item.quantidade,
        })
    return _salvar_carrinho(carrinho)


@api.post("/api/carrinho/{carrinho_id}/finalizar", status_code=201, tags=["carrinho"])
def finalizar_carrinho(carrinho_id: str) -> dict[str, Any]:
    carrinho = _carregar_carrinho(carrinho_id)
    if not carrinho["itens"]:
        raise HTTPException(status_code=422, detail="carrinho vazio")
    try:
        pedido = banco.registrar_pedido(carrinho_id, carrinho["itens"])
    except EstoqueInsuficiente as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    cache.apagar(_chave_carrinho(carrinho_id))
    try:
        cache.apagar(CHAVE_PRODUTOS)  # o estoque mudou
    except CacheIndisponivel:
        pass
    return pedido


@api.get("/api/pedidos", tags=["carrinho"])
def listar_pedidos() -> list[dict[str, Any]]:
    return banco.listar_pedidos()


# --------------------------------------------------------------------- front
@api.get("/", include_in_schema=False)
def pagina_inicial() -> FileResponse:
    return FileResponse(ESTATICO / "index.html")


api.mount("/static", StaticFiles(directory=ESTATICO), name="static")
