"""Métricas RED HTTP para exposição no Prometheus."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from prometheus_client import Counter, Histogram, make_asgi_app

REQUISICOES_HTTP = Counter(
    "http_requests_total",
    "Total de requisições HTTP por método, rota e status.",
    labelnames=("method", "route", "status"),
)
DURACAO_REQUISICOES_HTTP = Histogram(
    "http_duration_seconds",
    "Duração das requisições HTTP por método e rota.",
    labelnames=("method", "route"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
app_metricas = make_asgi_app()


class PrometheusMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["path"].startswith("/metrics"):
            await self.app(scope, receive, send)
            return

        inicio = perf_counter()
        status = 500

        async def send_with_status(message: dict[str, Any]) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            route = scope.get("route")
            rota = getattr(route, "path", "unmatched")
            metodo = scope["method"]
            REQUISICOES_HTTP.labels(
                method=metodo,
                route=rota,
                status=str(status),
            ).inc()
            DURACAO_REQUISICOES_HTTP.labels(method=metodo, route=rota).observe(
                perf_counter() - inicio
            )
