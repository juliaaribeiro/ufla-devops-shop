# Análise de incidente — Knight Capital (2012)

## 1. O que aconteceu

Em 1º de agosto de 2012, a Knight Capital fez uma atualização de seu sistema de negociação. A implantação foi realizada manualmente em oito servidores, mas um deles permaneceu com a versão antiga do código. Além disso, uma funcionalidade antiga foi ativada por uma configuração que havia sido reutilizada. Como consequência, o sistema começou a realizar operações de forma incorreta e a empresa perdeu aproximadamente US$ 440 milhões em apenas 45 minutos. O problema não estava apenas no código, mas principalmente no processo de implantação, que não garantia que todos os servidores estivessem com a mesma versão e não possuía validações suficientes.

## 2. Qual das Três Vias falhou e por quê?

A **Primeira Via — Fluxo** foi a principal via que falhou.

A Primeira Via busca otimizar o fluxo de trabalho até o usuário, tornando o trabalho visível, reduzindo o tamanho dos lotes e evitando que defeitos sejam levados para as próximas etapas. No caso da Knight Capital, a implantação manual em oito servidores permitiu que um servidor permanecesse com uma versão diferente dos demais. Isso significa que o processo não garantia um estado consistente após a implantação.

Além disso, a ausência de validação automática fez com que o problema chegasse à produção. O material destaca justamente que a causa raiz do incidente foi a falta de uma implantação automatizada e verificável.

Também existe uma relação com a **Segunda Via — Feedback**, pois um processo com validações e feedback mais rápidos poderia ter identificado o problema antes que ele causasse um impacto tão grande.

## 3. Quais métricas DORA teriam denunciado o problema antes?

As quatro métricas DORA poderiam ajudar a identificar problemas no processo:

* **Frequência de implantação:** uma implantação mais frequente e com mudanças menores reduziria o tamanho do lote e facilitaria a identificação de problemas.
* **Lead time para mudanças:** um processo automatizado poderia reduzir o tempo entre a alteração do código e sua disponibilização, diminuindo a dependência de procedimentos manuais.
* **Taxa de falha em mudanças:** essa métrica mostraria quantas implantações estavam causando problemas. Uma taxa elevada indicaria que o processo de implantação precisava ser melhorado.
* **Tempo médio de restauração:** indicaria quanto tempo a equipe levava para recuperar o sistema depois de uma falha.

A aula destaca que as quatro métricas devem ser analisadas em conjunto e que times de alto desempenho conseguem apresentar bons resultados tanto em velocidade quanto em estabilidade.

No caso da Knight Capital, principalmente a **taxa de falha em mudanças** e o **tempo de restauração** seriam importantes para demonstrar a fragilidade do processo.

## 4. Qual prática deste semestre teria evitado o dano e em qual semana ela será vista?

A prática que mais diretamente poderia ter evitado o incidente é a **implantação automatizada por meio de uma pipeline de CI/CD**, associada à utilização de ambientes reproduzíveis.

O problema aconteceu porque a implantação foi manual e um dos oito servidores ficou com uma versão diferente. Um processo automatizado poderia garantir que a mesma versão fosse implantada de forma consistente em todos os servidores e permitir validações antes da disponibilização.

De acordo com o roadmap apresentado na aula, **Git e GitHub serão trabalhados na semana 6**, enquanto a integração e entrega com **GitHub Actions** serão abordadas nas **semanas 6 e 7**. A disciplina também relaciona containers, pipeline de CI/CD e implantação automatizada à Primeira Via.
Portanto, a prática mais diretamente relacionada ao problema seria a **automação da entrega e implantação**, especialmente nas semanas **6 e 7**.

## 5. A cultura do relatório é generativa ou patológica?

A situação analisada aponta para a necessidade de uma **cultura generativa**, na qual os erros são investigados para melhorar o sistema em vez de simplesmente procurar um culpado.

A aula diferencia a cultura patológica, na qual informações ruins são escondidas e falhas geram caça às bruxas, da cultura generativa, na qual a informação é buscada, a responsabilidade é compartilhada e as falhas geram investigação e aprendizado.

Para esse tipo de incidente, uma abordagem generativa perguntaria **qual parte do processo permitiu que um servidor permanecesse com uma versão diferente e que uma funcionalidade antiga fosse ativada**, em vez de simplesmente procurar quem executou a implantação.

O próprio material recomenda que, após um incidente, o postmortem seja feito sem culpados e que a ação corretiva seja direcionada ao sistema, por meio de validação, automação e mecanismos de proteção.

Assim, a principal lição do caso da Knight Capital é que confiabilidade não depende apenas de escrever código correto. É necessário construir um processo de entrega que seja automatizado, verificável e capaz de detectar e reverter problemas rapidamente.
