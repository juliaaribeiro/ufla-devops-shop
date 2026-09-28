// Front do ufla-devops-shop: JavaScript puro, sem build. Fala com a API em /api.
const $ = (sel) => document.querySelector(sel);
let carrinho = null;

const brl = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function avisar(texto, tipo = "ok") {
  const m = $("#mensagem");
  m.textContent = texto;
  m.className = `mensagem ${tipo}`;
}

async function chamar(caminho, opcoes = {}) {
  const resp = await fetch(caminho, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });
  const corpo = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(corpo.detail || `HTTP ${resp.status}`);
  return corpo;
}

function renderizarProdutos(lista) {
  const grade = $("#produtos");
  grade.innerHTML = "";
  if (!lista.length) {
    grade.innerHTML = "<p>Nenhum produto encontrado.</p>";
    return;
  }
  for (const p of lista) {
    const card = document.createElement("article");
    card.className = "produto";
    card.innerHTML = `
      <h3>${p.nome}</h3>
      <p class="desc">${p.descricao}</p>
      <p class="preco">${brl(p.preco)}</p>
      <p class="estoque">${p.estoque} em estoque</p>
      <button ${p.estoque === 0 ? "disabled" : ""}>Adicionar</button>`;
    card.querySelector("button").addEventListener("click", () => adicionar(p.id));
    grade.appendChild(card);
  }
}

function renderizarCarrinho() {
  const ul = $("#itens");
  ul.innerHTML = "";
  const itens = carrinho ? carrinho.itens : [];
  for (const i of itens) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${i.quantidade}× ${i.nome}</span><span>${brl(i.preco * i.quantidade)}</span>`;
    ul.appendChild(li);
  }
  $("#total").textContent = brl(carrinho ? carrinho.total : 0);
  $("#finalizar").disabled = itens.length === 0;
}

async function carregarProdutos(termo = "") {
  try {
    const dados = termo
      ? (await chamar(`/api/busca?q=${encodeURIComponent(termo)}`)).resultados
      : await chamar("/api/produtos");
    renderizarProdutos(dados);
  } catch (e) {
    avisar(`Falha ao carregar produtos: ${e.message}`, "erro");
  }
}

async function garantirCarrinho() {
  if (carrinho) return carrinho;
  carrinho = await chamar("/api/carrinho", { method: "POST" });
  return carrinho;
}

async function adicionar(produtoId) {
  try {
    await garantirCarrinho();
    carrinho = await chamar(`/api/carrinho/${carrinho.id}/itens`, {
      method: "POST",
      body: JSON.stringify({ produto_id: produtoId, quantidade: 1 }),
    });
    renderizarCarrinho();
    avisar("Item adicionado.");
  } catch (e) {
    if (/não encontrado ou expirado/.test(e.message)) carrinho = null;
    avisar(e.message, "erro");
  }
}

async function finalizar() {
  try {
    const pedido = await chamar(`/api/carrinho/${carrinho.id}/finalizar`, { method: "POST" });
    carrinho = null;
    renderizarCarrinho();
    avisar(`Pedido #${pedido.id} fechado: ${brl(pedido.total)}.`);
    carregarProdutos($("#termo").value.trim());
  } catch (e) {
    avisar(e.message, "erro");
  }
}

async function mostrarInfo() {
  try {
    const i = await chamar("/api/info");
    $("#info").textContent =
      `v${i.versao} · banco: ${i.banco} · cache: ${i.cache} · instância: ${i.instancia}`;
  } catch {
    $("#info").textContent = "API fora do ar";
  }
}

$("#busca").addEventListener("submit", (ev) => {
  ev.preventDefault();
  carregarProdutos($("#termo").value.trim());
});
$("#limpar").addEventListener("click", () => {
  $("#termo").value = "";
  carregarProdutos();
});
$("#finalizar").addEventListener("click", finalizar);

mostrarInfo();
carregarProdutos();
renderizarCarrinho();
