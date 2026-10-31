# 11 — Gerador de conversas de exemplo + as 5 conversas

**What to build:** o desenvolvedor roda um comando que executa roteiros de conversa contra o modelo real, com Data de referência fixa, e grava cada conversa em Markdown junto do trecho correspondente do log de auditoria. Quem visita o repositório lê as 5 conversas sem precisar rodar o projeto.

**Blocked by:** 04 — Detalhe do Produto; 05 — Manual de políticas e situação da loja; 06 — Consulta de Pedido; 07 — Registro de Reclamação; 08 — Log de auditoria; 09 — Robustez do loop

**Status:** ready-for-agent

**Executor:** builder (código do gerador) + humano (execução contra o modelo real, com chave e custo; o agente só implementa o gerador).

**Gates:** Assíncrono/integrações (LLM real); logging seguro (conversas publicadas mascaradas). Ordem de execução: 11 de 12.

- [ ] Comando único regenera todas as conversas com `AGENT_NOW=2026-03-23T10:00:00-04:00` (segunda-feira logo após o último Pedido do conjunto de dados) e temperatura 0
- [ ] Cada conversa em Markdown com as falas e o trecho do log (ferramentas escolhidas, argumentos, resultados), mascarado
- [ ] As 5 conversas: (1) violões até R$ 1000 — busca + PIX + esgotado, com follow-up roteirizado sobre o Giannini GF-3D (13 resultados; o GF-3D fica fora dos 5 primeiros); (2) Takamine GD20 com Promoção expirada; (3) devolução do Pedido 7 com Verificação do pedido por `leticia.rocha@jmail.com` e prazos de pós-venda calculados (arrependimento vencido, garantia legal vigente); (4) Acessórios + pergunta Fora de escopo; (5) Reclamação com Protocolo
- [ ] Teste de fumaça do gerador com LLM falso (formato do Markdown), sem rede
- [ ] Conversas revisadas manualmente: nenhum preço, estoque ou prazo inventado; parcelamento, se citado, conferido com as faixas da seção 3.1
