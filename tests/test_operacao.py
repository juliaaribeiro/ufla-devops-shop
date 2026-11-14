def test_health_responde_sem_dependencias(cliente):
    resp = cliente.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "versao" in resp.json()


def test_ready_ok_no_modo_autonomo(cliente):
    resp = cliente.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "banco": "ok", "cache": "ok"}


def test_info_descreve_o_modo(cliente):
    dados = cliente.get("/api/info").json()
    assert dados["banco"] == "sqlite"
    assert dados["cache"] == "memoria"
    assert dados["instancia"]


def test_rota_de_erro_devolve_500(cliente):
    resp = cliente.get("/api/erro")
    assert resp.status_code == 500
    assert "proposital" in resp.json()["detail"]


def test_metricas_red_incluem_rota_status_e_histograma(cliente):
    resp = cliente.get("/api/erro")
    assert resp.status_code == 500

    metricas = cliente.get("/metrics")
    assert metricas.status_code == 200
    assert 'http_requests_total{method="GET",route="/api/erro",status="500"}' in metricas.text
    assert "# TYPE http_duration_seconds histogram" in metricas.text
    assert 'http_duration_seconds_count{method="GET",route="/api/erro"}' in metricas.text
    assert 'route="/metrics"' not in metricas.text


def test_pagina_inicial_e_html(cliente):
    resp = cliente.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "ufla-devops-shop" in resp.text
