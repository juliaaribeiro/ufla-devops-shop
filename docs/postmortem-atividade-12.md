# Postmortem — Incidente de erro 5xx

> Preencher com os horários, saídas e medidas obtidos durante a simulação no
> cluster. A sessão de implementação não tinha contexto Kubernetes ativo;
> portanto, nenhum disparo de alerta ou impacto real é declarado aqui.

## Resumo

Simulação didática da rota existente `/api/erro`, que devolve HTTP 500. Preencha
data, duração, cluster/namespace e resultado após executar
`scripts/atividade-12-simular-incidente.sh`.

## Impacto

- Janela do incidente: **preencher com horário observado**.
- Proporção e volume de respostas 5xx: **registrar no Prometheus/Grafana**.
- Rotas e usuários afetados: **registrar; na simulação, espera-se a rota de erro**.
- Dados perdidos ou corrompidos: **confirmar após a simulação**.

## Linha do tempo

| Horário | Evento |
|---|---|
| preencher | Início da geração de tráfego para `/api/erro` |
| preencher | Dashboard passou a mostrar respostas 5xx |
| preencher | Alerta `TaxaDeErroAlta` disparou após `for: 10m` |
| preencher | Rota e causa da falha confirmadas |
| preencher | Geração de tráfego interrompida |
| preencher | Taxa de erro e alerta normalizados |

## Causas contribuintes

- A rota `/api/erro` foi criada intencionalmente para simular falhas HTTP 500.
- A simulação gera carga contínua; o tempo de alerta inclui a avaliação do Prometheus
  e a persistência de 10 minutos configurada.
- Adicionar outras condições contribuintes somente se forem comprovadas pelas
  métricas, logs e eventos observados.

## O que funcionou

- Preencher após verificar a coleta do Prometheus, o dashboard, o alerta e o
  runbook no cluster.

## O que não funcionou

- Registrar somente falhas observadas durante a execução; não presumir falhas.

## Ações

| Ação | Responsável | Prazo | Status |
|---|---|---|---|
| Guardar a saída do gerador e capturas do Prometheus/Grafana no diretório de evidências | Estudante responsável | Até a entrega da atividade | Pendente |
| Confirmar que a regra dispara após 10 min e resolver após o fim do tráfego | Responsável pelo laboratório | Até a entrega da atividade | Pendente |
| Revisar o acesso à rota `/api/erro` antes de usar a aplicação fora do laboratório | Responsável pela aplicação | Antes de qualquer publicação externa | Pendente |
