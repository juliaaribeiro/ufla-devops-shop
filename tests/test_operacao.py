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


def test_pagina_inicial_e_html(cliente):
    resp = cliente.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "ufla-devops-shop" in resp.text
