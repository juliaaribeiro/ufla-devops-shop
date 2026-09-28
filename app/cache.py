"""Cache: Redis quando ``REDIS_URL`` esta definida, memoria do processo caso contrario.

O cache guarda duas coisas: a lista de produtos (com TTL curto, para aliviar o
banco) e os carrinhos (sem TTL longo: um carrinho abandonado expira em 1 h).

Atencao ao modo memoria: cada replica tem o seu proprio dicionario. Com 3
replicas no Kubernetes e sem Redis, um carrinho criado numa replica nao existe
nas outras --- e exatamente o problema que o Redis resolve na Atividade 10.
"""

from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger("loja.cache")


class CacheIndisponivel(Exception):
    """O Redis nao respondeu."""


class Cache:
    def __init__(self, redis_url: str) -> None:
        self.modo = "redis" if redis_url else "memoria"
        self._memoria: dict[str, tuple[float, str]] = {}
        self._trava = threading.Lock()
        self._redis = None
        if redis_url:
            import redis

            self._redis = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )

    def _chamar(self, operacao, *args, **kwargs):
        import redis

        try:
            return operacao(*args, **kwargs)
        except redis.exceptions.RedisError as exc:
            raise CacheIndisponivel(str(exc)) from exc

    def obter(self, chave: str) -> str | None:
        if self._redis is not None:
            return self._chamar(self._redis.get, chave)
        with self._trava:
            item = self._memoria.get(chave)
            if item is None:
                return None
            expira_em, valor = item
            if expira_em < time.monotonic():
                del self._memoria[chave]
                return None
            return valor

    def guardar(self, chave: str, valor: str, ttl: int) -> None:
        if self._redis is not None:
            self._chamar(self._redis.set, chave, valor, ex=ttl)
            return
        with self._trava:
            self._memoria[chave] = (time.monotonic() + ttl, valor)

    def apagar(self, chave: str) -> None:
        if self._redis is not None:
            self._chamar(self._redis.delete, chave)
            return
        with self._trava:
            self._memoria.pop(chave, None)

    def ping(self) -> bool:
        if self._redis is None:
            return True
        try:
            return bool(self._redis.ping())
        except Exception as exc:  # noqa: BLE001 - o ping so informa
            log.warning("cache sem resposta: %s", exc)
            return False
