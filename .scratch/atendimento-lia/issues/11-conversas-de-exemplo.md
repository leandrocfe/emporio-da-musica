# 11 — Gerador de conversas de exemplo + as 5 conversas

**What to build:** o desenvolvedor roda um comando que executa roteiros de conversa contra o modelo real, com Data de referência fixa, e grava cada conversa em Markdown junto do trecho correspondente do log de auditoria. Quem visita o repositório lê as 5 conversas sem precisar rodar o projeto.

**Blocked by:** 04 — Detalhe do Produto; 05 — Manual de políticas e situação da loja; 06 — Consulta de Pedido; 07 — Registro de Reclamação; 08 — Log de auditoria; 09 — Robustez do loop

**Status:** ready-for-human

**Executor:** builder (código do gerador) + humano (execução contra o modelo real, com chave e custo; o agente só implementa o gerador).

**Gates:** Assíncrono/integrações (LLM real); logging seguro (conversas publicadas mascaradas). Ordem de execução: 12 de 13.

- [x] Comando único regenera todas as conversas com `AGENT_NOW=2026-03-23T10:00:00-04:00` (segunda-feira logo após o último Pedido do conjunto de dados) e temperatura 0 (implementado; execução real contra o modelo pendente, a cargo do humano)
- [x] Cada conversa em Markdown com as falas e o trecho do log (ferramentas escolhidas, argumentos, resultados), mascarado
- [x] Roteiros das 5 conversas implementados (arquivos gerados pendentes de execução humana): (1) violões até R$ 1000 — busca + PIX + esgotado, com follow-up roteirizado sobre o Giannini GF-3D (13 resultados; o GF-3D fica fora dos 5 primeiros); (2) Takamine GD20 com Promoção expirada; (3) devolução do Pedido 7 com Verificação do pedido por `leticia.rocha@jmail.com` e prazos de pós-venda calculados (arrependimento vencido, garantia legal vigente); (4) Acessórios + pergunta Fora de escopo; (5) Reclamação com Protocolo
- [x] Teste de fumaça do gerador com LLM falso (formato do Markdown), sem rede
- [ ] Conversas revisadas manualmente: nenhum preço, estoque ou prazo inventado; parcelamento, se citado, conferido com as faixas da seção 3.1

## Comments

Gerador implementado em `src/emporio/examples.py` (roteiros como dados em `SCRIPTS`), testes em `tests/test_examples.py`. As conversas **não foram geradas**: exigem chave e custo. Para gerar (com `LLM_MODEL` e a chave do provedor no `.env`):

```bash
uv run --env-file .env python -m emporio.examples
```

Escreve `docs/conversas/*.md` (uma por roteiro, mais um `README.md` índice). Data de referência e temperatura 0 são fixas no código. Se o modelo falhar em qualquer conversa, nada é gravado. Depois de gerar, falta a revisão manual (último critério).

Para a revisão manual: (a) se o modelo usar `limit` >= 10 na busca do roteiro 1, o GF-3D entra na lista e o follow-up perde o sentido de "produto fora da lista"; (b) resultados acima de `max_result_chars` aparecem como `{"truncated": true, ...}` no trecho do log (limite do log real, não defeito do gerador); (c) nomes em texto livre e o primeiro nome da Cliente nas respostas da Lia não são mascarados (limitação do `masking.py`).

**Primeira passada na revisão (2026-11-01, agente):** as 5 conversas foram geradas com `gemini-3.8-flash`. Conferido contra o log e os dados: preços e PIX iguais aos resultados das ferramentas; GF-3D fora dos 5 primeiros e esgotado, sem citar as Promoções expiradas; Takamine GD20 sem promoção, 12x de R$ 183,25 dentro da seção 3.1, combinação PIX + cartão acima de R$ 2.000 consta no Manual (3.x); prazos do Pedido 7 iguais aos calculados (24/02, 05/03, 18/05) e garantia com o fabricante após 30 dias consta no Manual; Acessórios e Fora de escopo recusados; Protocolo `EMP-20260323-KFPJE3`. Único enfeite: "som encorpado" no GF-1R (a descrição diz "som equilibrado"). Falta a revisão do mantenedor para marcar o último critério.
