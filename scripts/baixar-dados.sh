#!/usr/bin/env bash
#
# baixar-dados.sh -- DevOps na Prática (DCC/UFLA)
#
# Baixa o access.log da Atividade 2 e confere a integridade dele.
# O arquivo não é versionado: 87 MB não entram em Git. Ele vive como asset
# de uma release do repositório da turma.
#
#   Uso:  ./scripts/baixar-dados.sh
#
#   Código de saída:  0 = dados prontos em dados/access.log
#                     1 = falhou (rede, checksum ou ferramenta ausente)
#
# Idempotente: se o arquivo já existe e o checksum bate, não baixa de novo.
# ---------------------------------------------------------------------------

set -uo pipefail

URL="https://github.com/rdurelli/ufla-devops-shop/releases/download/dados-v1/access.log.gz"
DESTINO="dados/access.log"
SHA_ESPERADO="1f9ddae0a4320c3d4a8dfdb2200959e7d99b562ef2f03c1ae5ff5469e42259ae"
LINHAS_ESPERADAS=516866

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    VERDE=$'\033[0;32m'; VERMELHO=$'\033[0;31m'; NEGRITO=$'\033[1m'; RESET=$'\033[0m'
else
    VERDE=''; VERMELHO=''; NEGRITO=''; RESET=''
fi

ok()   { printf '%s[ok]%s      %s\n' "$VERDE" "$RESET" "$1"; }
erro() { printf '%s[ERRO]%s    %s\n' "$VERMELHO" "$RESET" "$1" >&2; }

# --- soma de verificação, com o comando que existir na máquina --------------
# macOS traz 'shasum'; a maioria das distribuições Linux traz 'sha256sum'.
soma() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d' ' -f1
    else
        erro "nem sha256sum nem shasum encontrados -- instale coreutils"
        exit 1
    fi
}

printf '%s== Dados da Atividade 2 -- DevOps na Pratica ==%s\n\n' "$NEGRITO" "$RESET"

# --- já está aqui? ----------------------------------------------------------
if [ -f "$DESTINO" ] && [ "$(soma "$DESTINO")" = "$SHA_ESPERADO" ]; then
    ok "dados/access.log ja presente e integro -- nada a fazer"
    printf '\nLinhas: %s\n' "$(wc -l < "$DESTINO" | tr -d ' ')"
    exit 0
fi

command -v curl >/dev/null 2>&1 || { erro "curl nao encontrado"; exit 1; }
command -v gunzip >/dev/null 2>&1 || { erro "gunzip nao encontrado"; exit 1; }

mkdir -p dados

# --- baixar -----------------------------------------------------------------
printf 'Baixando ~5 MB de %s\n' "$URL"
if ! curl -fSL --retry 3 --retry-delay 2 -o "$DESTINO.gz" "$URL"; then
    erro "falha no download -- verifique a sua conexao e tente de novo"
    rm -f "$DESTINO.gz"
    exit 1
fi
ok "download concluido"

# --- descompactar -----------------------------------------------------------
rm -f "$DESTINO"
if ! gunzip "$DESTINO.gz"; then
    erro "falha ao descompactar $DESTINO.gz"
    exit 1
fi
ok "arquivo descompactado (~87 MB)"

# --- conferir ---------------------------------------------------------------
SHA_OBTIDO="$(soma "$DESTINO")"
if [ "$SHA_OBTIDO" != "$SHA_ESPERADO" ]; then
    erro "checksum nao confere -- o arquivo veio corrompido"
    erro "  esperado: $SHA_ESPERADO"
    erro "  obtido:   $SHA_OBTIDO"
    erro "Apague dados/access.log e rode este script de novo."
    exit 1
fi
ok "checksum confere"

LINHAS="$(wc -l < "$DESTINO" | tr -d ' ')"
if [ "$LINHAS" != "$LINHAS_ESPERADAS" ]; then
    erro "contagem de linhas inesperada: $LINHAS (esperado $LINHAS_ESPERADAS)"
    exit 1
fi
ok "$LINHAS linhas"

printf '\nPronto. Os dados estao em %s\n' "$DESTINO"
printf 'Lembre-se: %s NAO deve ser versionado -- ja esta no .gitignore.\n' "$DESTINO"
