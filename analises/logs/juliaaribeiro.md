# Análise do access.log

## 1. Total de requisições e falhas

O arquivo `dados/access.log` possui **516.866 requisições** no total.

Foram identificadas:

* **6.162 requisições com erro 4xx**
* **11.749 requisições com erro 5xx**
* **17.911 requisições com falha no total**

### Pipeline utilizado

```bash
wc -l dados/access.log
```

```bash
awk '$9 ~ /^4[0-9][0-9]$/ {count++} END {print count}' dados/access.log
```

```bash
awk '$9 ~ /^5[0-9][0-9]$/ {count++} END {print count}' dados/access.log
```

### Conclusão

De um total de **516.866 requisições**, **17.911 apresentaram códigos de erro 4xx ou 5xx**. Isso representa aproximadamente **3,47%** das requisições analisadas.

---

## 2. IPs mais frequentes e identificação de comportamento suspeito

Os 10 IPs que mais realizaram requisições foram:

| Posição | IP             | Requisições |
| ------- | -------------- | ----------: |
| 1       | `203.0.113.47` |  **88.400** |
| 2       | `192.0.2.245`  |       1.788 |
| 3       | `192.0.2.171`  |       1.772 |
| 4       | `192.0.2.81`   |       1.771 |
| 5       | `192.0.2.225`  |       1.771 |
| 6       | `192.0.2.16`   |       1.771 |
| 7       | `192.0.2.138`  |       1.767 |
| 8       | `192.0.2.222`  |       1.762 |
| 9       | `192.0.2.45`   |       1.757 |
| 10      | `192.0.2.166`  |       1.753 |

### Pipeline utilizado

```bash
awk '{print $1}' dados/access.log | sort | uniq -c | sort -nr | awk 'NR <= 10'
```

O IP `203.0.113.47` apresentou um comportamento muito discrepante em relação aos demais. Enquanto o segundo IP mais frequente realizou 1.788 requisições, esse IP realizou **88.400**, aproximadamente 49 vezes mais.

Para investigar o comportamento, foi analisado quais endpoints esse IP acessou:

```bash
awk '$1 == "203.0.113.47" {print $7}' dados/access.log | sort | uniq -c | sort -nr | head -20
```

Resultado:

| Endpoint                | Requisições |
| ----------------------- | ----------: |
| `/api/busca?q=mochila`  |      22.224 |
| `/api/busca?q=tenis`    |      22.161 |
| `/api/busca?q=camiseta` |      22.090 |
| `/api/busca?q=fone`     |      21.925 |

### Conclusão

O `203.0.113.47` apresenta **indícios de comportamento automatizado ou abusivo**, pois concentrou **88.400 requisições** em apenas quatro consultas repetitivas da API de busca.

A concentração e o volume são muito superiores aos dos demais IPs. Entretanto, os dados do log, isoladamente, não permitem afirmar com certeza que se trata de um ataque. O mais adequado é classificá-lo como **IP suspeito, com comportamento compatível com automação ou abuso da API**.

---

## 3. Endpoint que causou mais erros 500

O endpoint que apresentou a maior quantidade de erros HTTP 500 foi:

**`/api/relatorio/gerar` — 3.620 erros 500**

Os 10 endpoints com mais erros 500 foram:

| Posição | Endpoint               | Erros 500 |
| ------- | ---------------------- | --------: |
| 1       | `/api/relatorio/gerar` | **3.620** |
| 2       | `/`                    |       228 |
| 3       | `/api/produtos`        |       167 |
| 4       | `/produtos`            |       160 |
| 5       | `/produtos/detalhe`    |       150 |
| 6       | `/static/app.css`      |       117 |
| 7       | `/static/app.js`       |       105 |
| 8       | `/api/carrinho`        |        92 |
| 9       | `/api/busca`           |        63 |
| 10      | `/favicon.ico`         |        44 |

### Pipeline utilizado

```bash
awk '$9 == 500 {print $7}' dados/access.log | sort | uniq -c | sort -nr | awk 'NR <= 10'
```

### Conclusão

O endpoint `/api/relatorio/gerar` é o principal ponto de atenção em relação aos erros internos. Ele apresentou **3.620 erros 500**, uma quantidade muito superior à dos demais endpoints analisados.

Esse comportamento sugere que o endpoint deve ser priorizado em uma investigação técnica para identificar a causa dos erros.

---

## 4. Horário de pico de tráfego

O horário com maior volume de requisições foi **23h**, com **68.535 requisições**.

Os principais horários foram:

| Horário | Requisições |
| ------- | ----------: |
| **23h** |  **68.535** |
| 22h     |      43.979 |
| 15h     |      32.529 |
| 11h     |      32.526 |
| 12h     |      31.895 |
| 14h     |      31.225 |
| 16h     |      30.886 |
| 10h     |      30.869 |
| 13h     |      29.952 |
| 17h     |      28.575 |

### Pipeline utilizado

```bash
awk '{print substr($4, 14, 2)}' dados/access.log | sort | uniq -c | sort -nr
```

### Conclusão

O maior pico de tráfego ocorreu às **23h**, quando foram registradas **68.535 requisições**. Esse volume é significativamente superior ao segundo maior pico, registrado às 22h, com 43.979 requisições.

Esse horário deve ser considerado em análises de capacidade e comportamento do sistema.

---

## 5. Tentativas de acesso a caminhos sensíveis

Foram encontradas tentativas de acesso a caminhos potencialmente sensíveis relacionados a `/admin`, `.env` e `.git`.

| Caminho        | Tentativas |
| -------------- | ---------: |
| `/admin/login` |        382 |
| `/.git/config` |        356 |
| `/.env`        |        343 |
| `/admin`       |        313 |
| **Total**      |  **1.394** |

### Pipeline utilizado

```bash
grep -E '(/admin|/\.env|/\.git)' dados/access.log | awk '{print $7}' | sort | uniq -c | sort -nr
```

### Conclusão

Sim. Existem **1.394 tentativas de acesso a caminhos sensíveis**.

Os acessos a `/.env` e `/.git/config` merecem atenção especial, pois, caso esses arquivos estejam expostos, podem revelar informações de configuração, credenciais ou dados do repositório. As tentativas de acesso a `/admin` e `/admin/login` também indicam procura por áreas administrativas da aplicação.

---

# Conclusão geral

A análise das **516.866 requisições** do `access.log` revelou alguns pontos relevantes:

* Foram registradas **17.911 requisições com erros 4xx ou 5xx**.
* O IP `203.0.113.47` apresentou comportamento **fortemente discrepante**, com **88.400 requisições**, concentradas principalmente em consultas repetitivas à API de busca.
* O endpoint **`/api/relatorio/gerar`** concentrou a maior quantidade de erros 500, com **3.620 ocorrências**.
* O maior volume de tráfego ocorreu às **23h**, com **68.535 requisições**.
* Foram identificadas **1.394 tentativas de acesso a caminhos sensíveis**, incluindo `/admin`, `/.env` e `/.git/config`.

Com base nesses dados, os principais pontos que merecem investigação são o comportamento do IP `203.0.113.47`, a causa dos erros no endpoint `/api/relatorio/gerar` e as tentativas de acesso aos caminhos sensíveis da aplicação.
