# Atividade 8 — Pipeline seguro

Este repositório foi preparado com um pipeline de CI/CD que aplica os gates de segurança exigidos pela atividade.

## O que foi adicionado

- Gitleaks varrendo o histórico do Git antes da entrega.
- SonarCloud para análise de código novo com Quality Gate.
- Trivy em filesystem e sobre a imagem Docker construída.
- SBOM em SPDX JSON gerado pela imagem final e publicado como artifact.
- Documentação para demonstração de vulnerabilidade temporária em um PR de teste.

## Como demonstrar o bloqueio de uma dependência vulnerável

1. Crie a branch de teste:
   ```bash
   git switch -c atividade-08-demo
   ```
2. Instale uma dependência com correção disponível, mas vulnerável no momento do teste:
   ```bash
   python -m pip install "requests==2.19.1"
   ```
3. Registre isso em um arquivo de dependências do projeto, por exemplo usando `pip freeze > requirements.txt`, ou apenas em um ambiente de teste antes do PR.
4. Abra o Pull Request e execute o workflow.
5. A etapa de Trivy deve falhar com vulnerabilidade CRITICAL/HIGH e bloquear o merge.
6. Corrija para uma versão segura:
   ```bash
   python -m pip install "requests==2.32.3"
   python -m pip freeze > requirements.txt
   ```
7. Faça novo commit/push e confirme que o pipeline passa.
8. Remova a dependência temporária antes do merge final do PR.

## Observações importantes

- Os gates de segurança são bloqueantes por design.
- A imagem Docker só avança quando não há vulnerabilidades CRITICAL/HIGH corrigíveis.
- O arquivo SBOM é enviado como artifact do workflow para que o professor possa inspecionar o resultado.
- A dependência vulnerável foi deixada apenas em um ambiente de demonstração, nunca no branch final.

## Comandos úteis

```bash
python -m pip install -r requirements.txt
python -m compileall app scripts
```
