def test_busca_ignora_maiusculas(cliente):
    resp = cliente.get("/api/busca", params={"q": "CANECA"})
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["total"] >= 1
    assert all("caneca" in r["nome"].lower() for r in dados["resultados"])


def test_busca_na_descricao(cliente):
    dados = cliente.get("/api/busca", params={"q": "vinil"}).json()
    assert dados["total"] >= 2


def test_busca_sem_resultado(cliente):
    dados = cliente.get("/api/busca", params={"q": "zzzzzz"}).json()
    assert dados == {"termo": "zzzzzz", "total": 0, "resultados": []}


def test_busca_sem_termo_422(cliente):
    assert cliente.get("/api/busca").status_code == 422
    assert cliente.get("/api/busca", params={"q": ""}).status_code == 422
