import pytest


@pytest.fixture
def carrinho(cliente):
    resp = cliente.post("/api/carrinho")
    assert resp.status_code == 201
    return resp.json()


def test_carrinho_novo_vazio(carrinho):
    assert carrinho["itens"] == []
    assert carrinho["total"] == 0


def test_carrinho_inexistente_404(cliente):
    assert cliente.get("/api/carrinho/nao-existe").status_code == 404


def test_adicionar_item_soma_total(cliente, carrinho):
    produto = cliente.get("/api/produtos").json()[0]
    resp = cliente.post(f"/api/carrinho/{carrinho['id']}/itens",
                        json={"produto_id": produto["id"], "quantidade": 2})
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["itens"][0]["quantidade"] == 2
    assert dados["total"] == round(produto["preco"] * 2, 2)

    # adicionar o mesmo produto de novo acumula a quantidade
    dados = cliente.post(f"/api/carrinho/{carrinho['id']}/itens",
                         json={"produto_id": produto["id"], "quantidade": 1}).json()
    assert len(dados["itens"]) == 1
    assert dados["itens"][0]["quantidade"] == 3


def test_adicionar_produto_inexistente_404(cliente, carrinho):
    resp = cliente.post(f"/api/carrinho/{carrinho['id']}/itens",
                        json={"produto_id": 999999, "quantidade": 1})
    assert resp.status_code == 404


def test_adicionar_alem_do_estoque_409(cliente, carrinho):
    produto = cliente.post("/api/produtos",
                           json={"nome": "Peça rara", "preco": 10, "estoque": 1}).json()
    resp = cliente.post(f"/api/carrinho/{carrinho['id']}/itens",
                        json={"produto_id": produto["id"], "quantidade": 2})
    assert resp.status_code == 409


def test_finalizar_carrinho_vazio_422(cliente, carrinho):
    assert cliente.post(f"/api/carrinho/{carrinho['id']}/finalizar").status_code == 422


def test_finalizar_baixa_estoque_e_registra_pedido(cliente, carrinho):
    produto = cliente.post("/api/produtos",
                           json={"nome": "Produto do pedido", "preco": 20, "estoque": 5}).json()
    cliente.post(f"/api/carrinho/{carrinho['id']}/itens",
                 json={"produto_id": produto["id"], "quantidade": 3})

    resp = cliente.post(f"/api/carrinho/{carrinho['id']}/finalizar")
    assert resp.status_code == 201
    pedido = resp.json()
    assert pedido["total"] == 60.0
    assert pedido["itens"] == 3

    assert cliente.get(f"/api/produtos/{produto['id']}").json()["estoque"] == 2
    assert cliente.get(f"/api/carrinho/{carrinho['id']}").status_code == 404
    assert any(p["id"] == pedido["id"] for p in cliente.get("/api/pedidos").json())
