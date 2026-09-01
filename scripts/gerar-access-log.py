#!/usr/bin/env python3
"""
gerar-access-log.py -- DevOps na Prática (DCC/UFLA)

Gera o dataset da Atividade 2: um access.log no formato *combined* do Nginx
com sinais plantados, para que as cinco perguntas do enunciado tenham resposta
conhecida e verificável.

Esta é uma ferramenta DO PROFESSOR. O aluno nunca a executa -- ele baixa o
arquivo pronto com scripts/baixar-dados.sh.

    ./scripts/gerar-access-log.py --saida dados/access.log

A geração é determinística (semente fixa): rodar duas vezes produz byte a byte
o mesmo arquivo, e portanto o mesmo SHA-256 exigido por baixar-dados.sh.

Sinais plantados (o gabarito):

  P2  203.0.113.47 responde sozinho por ~17% das requisições, todas em
      /api/busca, com user-agent curl/8.5.0 -- um cliente em laço.
  P3  /api/relatorio/gerar tem taxa de erro 500 de ~35%; nenhum outro
      endpoint passa de 1%.
  P4  o pico de tráfego é às 23h (o laço do 203.0.113.47 começa às 22h).
  P5  198.51.100.9 e 198.51.100.23 varrem /admin, /.env, /.git/config,
      /wp-login.php e /phpmyadmin -- todos respondidos com 404.
"""

import argparse
import datetime as dt
import random

SEMENTE = 20262  # 2026/2

# --- catálogo de tráfego legítimo -------------------------------------------
ROTAS_OK = [
    ("/", 220), ("/produtos", 180), ("/produtos/detalhe", 140),
    ("/api/produtos", 160), ("/api/carrinho", 90), ("/api/busca", 70),
    ("/static/app.css", 120), ("/static/app.js", 120), ("/favicon.ico", 60),
    ("/checkout", 40), ("/api/pedidos", 45), ("/health", 30),
]
ROTA_QUEBRADA = "/api/relatorio/gerar"
CAMINHOS_SENSIVEIS = [
    "/admin", "/admin/login", "/.env", "/.git/config",
    "/wp-login.php", "/phpmyadmin/index.php",
]

AGENTES = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
]
AGENTE_LACO = "curl/8.5.0"
AGENTE_SCANNER = "python-requests/2.32.3"

# Faixas reservadas para documentação (RFC 5737) -- nenhum IP real.
def ip_normal(rnd):
    return "192.0.2.%d" % rnd.randint(1, 254)

IP_ABUSIVO = "203.0.113.47"
IPS_SCANNER = ["198.51.100.9", "198.51.100.23"]

MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Perfil de tráfego por hora (0..23). O pico às 23h vem do laço, somado depois.
PESO_HORA = [10, 6, 4, 3, 3, 4, 12, 30, 60, 85, 95, 100,
             98, 92, 96, 100, 95, 88, 80, 70, 58, 48, 40, 34]


def carimbo(rnd, hora):
    base = dt.datetime(2026, 8, 14, hora, 0, 0)
    momento = base + dt.timedelta(seconds=rnd.randint(0, 3599))
    return "%02d/%s/%d:%02d:%02d:%02d +0000" % (
        momento.day, MESES[momento.month - 1], momento.year,
        momento.hour, momento.minute, momento.second)


def linha(ip, quando, metodo, caminho, status, tamanho, agente):
    return '%s - - [%s] "%s %s HTTP/1.1" %d %d "-" "%s"\n' % (
        ip, quando, metodo, caminho, status, tamanho, agente)


def gerar(total, rnd):
    """Devolve a lista de linhas, já embaralhada dentro de cada hora."""
    rotas = []
    for caminho, peso in ROTAS_OK:
        rotas.extend([caminho] * peso)

    por_hora = {h: [] for h in range(24)}
    soma_peso = sum(PESO_HORA)

    # --- tráfego normal -----------------------------------------------------
    normais = int(total * 0.80)
    for h in range(24):
        quantas = int(normais * PESO_HORA[h] / soma_peso)
        for _ in range(quantas):
            caminho = rnd.choice(rotas)
            # ~1% de erro de fundo, distribuído
            sorte = rnd.random()
            if sorte < 0.006:
                status, tam = 404, rnd.randint(120, 400)
            elif sorte < 0.009:
                status, tam = 500, rnd.randint(120, 600)
            elif sorte < 0.013:
                status, tam = 403, rnd.randint(120, 400)
            else:
                status, tam = 200, rnd.randint(180, 24000)
            por_hora[h].append(linha(ip_normal(rnd), carimbo(rnd, h), "GET",
                                     caminho, status, tam,
                                     rnd.choice(AGENTES)))

    # --- P3: o endpoint que quebra ------------------------------------------
    quebradas = int(total * 0.02)
    for _ in range(quebradas):
        h = rnd.choices(range(24), weights=PESO_HORA)[0]
        if rnd.random() < 0.35:
            status, tam = 500, rnd.randint(120, 600)
        else:
            status, tam = 200, rnd.randint(2000, 60000)
        por_hora[h].append(linha(ip_normal(rnd), carimbo(rnd, h), "POST",
                                 ROTA_QUEBRADA, status, tam,
                                 rnd.choice(AGENTES)))

    # --- P2/P4: o cliente em laço, das 22h às 23h ---------------------------
    abusivas = int(total * 0.17)
    for i in range(abusivas):
        h = 22 if i < abusivas * 0.35 else 23
        termo = rnd.choice(["camiseta", "tenis", "mochila", "fone"])
        caminho = "/api/busca?q=%s" % termo
        # o servidor começa a engasgar sob a carga
        status, tam = (200, rnd.randint(400, 1800)) if rnd.random() < 0.92 \
            else (503, rnd.randint(120, 400))
        por_hora[h].append(linha(IP_ABUSIVO, carimbo(rnd, h), "GET",
                                 caminho, status, tam, AGENTE_LACO))

    # --- P5: a varredura ----------------------------------------------------
    for _ in range(int(total * 0.004)):
        h = rnd.choice([2, 3, 4, 5])
        por_hora[h].append(linha(rnd.choice(IPS_SCANNER), carimbo(rnd, h),
                                 "GET", rnd.choice(CAMINHOS_SENSIVEIS),
                                 404, rnd.randint(120, 300), AGENTE_SCANNER))

    saida = []
    for h in range(24):
        rnd.shuffle(por_hora[h])
        saida.extend(por_hora[h])
    return saida


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--saida", default="dados/access.log")
    p.add_argument("--linhas", type=int, default=520000)
    args = p.parse_args()

    rnd = random.Random(SEMENTE)
    linhas = gerar(args.linhas, rnd)
    with open(args.saida, "w", encoding="utf-8") as f:
        f.writelines(linhas)
    print("%s -- %d linhas" % (args.saida, len(linhas)))


if __name__ == "__main__":
    main()
