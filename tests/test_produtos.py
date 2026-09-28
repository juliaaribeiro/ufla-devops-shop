def test_carga_inicial_tem_produtos(cliente):
    produtos = cliente.get("/api/produtos").json()
    assert len(produtos) >= 12
    assert {"id", "nome", "preco", "estoque"} <= set(produtos[0])


def test_obter_produto_existente(cliente):
    primeiro = cliente.get("/api/produtos").json()[0]
    resp = cliente.get(f"/api/produtos/{primeiro['id']}")
    assert resp.status_code == 200
    assert resp.json()["nome"] == primeiro["nome"]


def test_obter_produto_inexistente_404(cliente):
    assert cliente.get("/api/produtos/999999").status_code == 404


def test_criar_produto_persiste_e_aparece_na_lista(cliente):
    novo = {"nome": "Teste de persistência", "descricao": "criado no teste",
            "preco": 12.5, "estoque": 3}
    resp = cliente.post("/api/produtos", json=novo)
    assert resp.status_code == 201
    criado = resp.json()
    assert criado["id"] > 0
    assert criado["preco"] == 12.5

    nomes = [p["nome"] for p in cliente.get("/api/produtos").json()]
    assert "Teste de persistência" in nomes


def test_criar_produto_invalido_422(cliente):
    assert cliente.post("/api/produtos", json={"nome": "x", "preco": 0}).status_code == 422
    assert cliente.post("/api/produtos", json={"nome": "Sem preço"}).status_code == 422
