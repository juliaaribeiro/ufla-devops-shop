"""Acesso ao banco de dados.

Dois modos, escolhidos pela presenca de ``DATABASE_URL``:

* **postgresql** --- via ``psycopg`` (uma conexao por requisicao, sem pool:
  simples de raciocinar e suficiente para a carga da disciplina);
* **sqlite** --- arquivo local, sem servico nenhum. E o modo autonomo.

O SQL e escrito uma vez com o marcador ``?`` e convertido para ``%s`` no
PostgreSQL. As poucas diferencas de dialeto ficam isoladas em ``_ESQUEMA``.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any

log = logging.getLogger("loja.banco")


class BancoIndisponivel(Exception):
    """O banco nao respondeu (servico fora, rede, credencial errada)."""


PRODUTOS_INICIAIS: list[tuple[str, str, float, int]] = [
    ("Caneca DevOps na Prática", "Cerâmica, 350 ml: 'funciona na minha máquina'", 39.90, 25),
    ("Camiseta UFLA Computação", "Algodão, tamanhos P a GG", 59.90, 40),
    ("Adesivo Docker", "Vinil, 8 cm, resistente a água", 4.50, 200),
    ("Adesivo Kubernetes", "Vinil, 8 cm, resistente a água", 4.50, 180),
    ("Moletom DCC", "Moletom com capuz, cinza, bordado", 149.90, 12),
    ("Garrafa térmica 500 ml", "Inox, mantém a temperatura por 8 h", 89.00, 30),
    ("Mousepad Terminal", "Estampa de terminal Linux, 40 x 20 cm", 34.90, 50),
    ("Caderno Postmortem", "Pautado, 96 folhas, capa dura", 29.90, 60),
    ("Boné Site Reliability", "Aba curva, ajustável", 49.90, 18),
    ("Chaveiro YAML", "Acrílico, 'indentação importa'", 9.90, 120),
    ("Livro: Engenharia de Software Contínua", "Edição da turma, 280 páginas", 79.00, 8),
    ("Kit de adesivos CI/CD", "Dez adesivos sortidos", 19.90, 75),
]

_ESQUEMA = {
    "postgresql": [
        """
        CREATE TABLE IF NOT EXISTS produtos (
            id        SERIAL PRIMARY KEY,
            nome      TEXT NOT NULL,
            descricao TEXT NOT NULL DEFAULT '',
            preco     NUMERIC(10, 2) NOT NULL CHECK (preco > 0),
            estoque   INTEGER NOT NULL DEFAULT 0 CHECK (estoque >= 0),
            criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pedidos (
            id          SERIAL PRIMARY KEY,
            carrinho_id TEXT NOT NULL,
            total       NUMERIC(10, 2) NOT NULL,
            itens       INTEGER NOT NULL,
            criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
    ],
    "sqlite": [
        """
        CREATE TABLE IF NOT EXISTS produtos (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nome      TEXT NOT NULL,
            descricao TEXT NOT NULL DEFAULT '',
            preco     REAL NOT NULL CHECK (preco > 0),
            estoque   INTEGER NOT NULL DEFAULT 0 CHECK (estoque >= 0),
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pedidos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            carrinho_id TEXT NOT NULL,
            total       REAL NOT NULL,
            itens       INTEGER NOT NULL,
            criado_em   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ],
}


def _normalizar(linha: dict[str, Any]) -> dict[str, Any]:
    """Deixa a linha igual nos dois modos: preco/total em float, data em ISO 8601."""
    saida = dict(linha)
    for campo in ("preco", "total"):
        if isinstance(saida.get(campo), Decimal):
            saida[campo] = float(saida[campo])
    if isinstance(saida.get("criado_em"), datetime):
        saida["criado_em"] = saida["criado_em"].isoformat()
    return saida


class Banco:
    def __init__(self, database_url: str, sqlite_path: str) -> None:
        self.url = database_url
        self.sqlite_path = sqlite_path
        self.modo = "postgresql" if database_url else "sqlite"
        self._esquema_pronto = False
        self._trava = threading.Lock()

    # ----------------------------------------------------------------- conexao
    @contextmanager
    def conexao(self) -> Iterator[Any]:
        if self.modo == "postgresql":
            import psycopg
            from psycopg.rows import dict_row

            try:
                con = psycopg.connect(self.url, connect_timeout=3, row_factory=dict_row)
            except psycopg.OperationalError as exc:
                raise BancoIndisponivel(str(exc).strip()) from exc
            try:
                with con:
                    yield con
            finally:
                con.close()
        else:
            try:
                con = sqlite3.connect(self.sqlite_path, timeout=5)
            except sqlite3.OperationalError as exc:
                raise BancoIndisponivel(str(exc)) from exc
            con.row_factory = sqlite3.Row
            try:
                yield con
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.modo == "postgresql" else sql

    def _todos(self, con: Any, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        cur = con.execute(self._sql(sql), params)
        return [_normalizar(dict(linha)) for linha in cur.fetchall()]

    def _um(self, con: Any, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        linhas = self._todos(con, sql, params)
        return linhas[0] if linhas else None

    # ------------------------------------------------------------------ esquema
    def garantir_esquema(self) -> None:
        """Cria as tabelas e a carga inicial. Idempotente: pode rodar N vezes."""
        if self._esquema_pronto:
            return
        with self._trava:
            if self._esquema_pronto:
                return
            with self.conexao() as con:
                for comando in _ESQUEMA[self.modo]:
                    con.execute(comando)
                total = self._um(con, "SELECT COUNT(*) AS n FROM produtos")
                if total and total["n"] == 0:
                    for nome, descricao, preco, estoque in PRODUTOS_INICIAIS:
                        con.execute(
                            self._sql(
                                "INSERT INTO produtos (nome, descricao, preco, estoque)"
                                " VALUES (?, ?, ?, ?)"
                            ),
                            (nome, descricao, preco, estoque),
                        )
                    log.info("carga inicial: %d produtos", len(PRODUTOS_INICIAIS))
            self._esquema_pronto = True
            log.info("banco pronto (modo %s)", self.modo)

    def ping(self) -> bool:
        try:
            with self.conexao() as con:
                con.execute("SELECT 1")
            return True
        except Exception as exc:  # noqa: BLE001 - o ping so informa
            log.warning("banco sem resposta: %s", exc)
            return False

    # ----------------------------------------------------------------- produtos
    def listar_produtos(self) -> list[dict[str, Any]]:
        self.garantir_esquema()
        with self.conexao() as con:
            return self._todos(con, "SELECT * FROM produtos ORDER BY id")

    def obter_produto(self, produto_id: int) -> dict[str, Any] | None:
        self.garantir_esquema()
        with self.conexao() as con:
            return self._um(con, "SELECT * FROM produtos WHERE id = ?", (produto_id,))

    def buscar_produtos(self, termo: str) -> list[dict[str, Any]]:
        self.garantir_esquema()
        padrao = f"%{termo.lower()}%"
        with self.conexao() as con:
            return self._todos(
                con,
                "SELECT * FROM produtos"
                " WHERE lower(nome) LIKE ? OR lower(descricao) LIKE ?"
                " ORDER BY id",
                (padrao, padrao),
            )

    def criar_produto(
        self, nome: str, descricao: str, preco: float, estoque: int
    ) -> dict[str, Any]:
        self.garantir_esquema()
        with self.conexao() as con:
            cur = con.execute(
                self._sql(
                    "INSERT INTO produtos (nome, descricao, preco, estoque)"
                    " VALUES (?, ?, ?, ?) RETURNING id"
                ),
                (nome, descricao, preco, estoque),
            )
            novo_id = cur.fetchone()[0] if self.modo == "sqlite" else cur.fetchone()["id"]
            produto = self._um(con, "SELECT * FROM produtos WHERE id = ?", (novo_id,))
            assert produto is not None
            return produto

    # ------------------------------------------------------------------ pedidos
    def registrar_pedido(self, carrinho_id: str, itens: list[dict[str, Any]]) -> dict[str, Any]:
        """Baixa o estoque de cada item e grava o pedido, tudo na mesma transacao."""
        self.garantir_esquema()
        with self.conexao() as con:
            total = 0.0
            quantidade_total = 0
            for item in itens:
                cur = con.execute(
                    self._sql(
                        "UPDATE produtos SET estoque = estoque - ?"
                        " WHERE id = ? AND estoque >= ?"
                    ),
                    (item["quantidade"], item["produto_id"], item["quantidade"]),
                )
                if cur.rowcount != 1:
                    raise EstoqueInsuficiente(item["produto_id"])
                total += item["preco"] * item["quantidade"]
                quantidade_total += item["quantidade"]
            cur = con.execute(
                self._sql(
                    "INSERT INTO pedidos (carrinho_id, total, itens)"
                    " VALUES (?, ?, ?) RETURNING id"
                ),
                (carrinho_id, round(total, 2), quantidade_total),
            )
            pedido_id = cur.fetchone()[0] if self.modo == "sqlite" else cur.fetchone()["id"]
            pedido = self._um(con, "SELECT * FROM pedidos WHERE id = ?", (pedido_id,))
            assert pedido is not None
            return pedido

    def listar_pedidos(self) -> list[dict[str, Any]]:
        self.garantir_esquema()
        with self.conexao() as con:
            return self._todos(con, "SELECT * FROM pedidos ORDER BY id DESC")


class EstoqueInsuficiente(Exception):
    def __init__(self, produto_id: int) -> None:
        super().__init__(f"estoque insuficiente para o produto {produto_id}")
        self.produto_id = produto_id
