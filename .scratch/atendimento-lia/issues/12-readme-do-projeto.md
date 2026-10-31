# 12 — README do projeto

**What to build:** quem chega ao repositório abre o README em português e entende como rodar o projeto (Docker e local), como trocar o provedor de LLM, por que cada escolha técnica foi feita, quais suposições foram tomadas sobre os dados e o manual, como auditar pelo log, as limitações conhecidas e como assistentes de código foram usados.

**Blocked by:** 10 — Chat com identidade visual da loja; 11 — Gerador de conversas de exemplo + as 5 conversas

**Status:** ready-for-agent

**Executor:** builder — documentação com justificativas, não mecânica.

**Gates:** nenhum gate de superfície. Ordem de execução: 12 de 12. ADRs: 0001–0005 (referenciados).

- [ ] Como rodar: Docker (`cp .env.example .env`, informar a chave, comando único) e local com `uv`; testes sem chave/rede
- [ ] Configuração: `LLM_MODEL`, chaves por provedor, `AGENT_NOW`, `DB_PATH`
- [ ] Decisões justificadas, com links para os ADRs: LiteLLM + loop explícito em vez de framework/MCP; Manual inteiro no contexto em vez de RAG (com limiar em que RAG passaria a valer); ferramentas fixas em vez de agente SQL; SQLite; Chainlit; prazos de pós-venda em código
- [ ] Tratamento de dados e suposições: contradições do manual resolvidas (incluindo troca por defeito contada da compra, "Black Friday em todo o catálogo", "mais de 300 instrumentos"); divergências preservadas (Pedidos 3 e 20, PIX sem 5% nos Pedidos, `coming_soon` em Pedido entregue, categorias vazias, e-mail duplicado, Produtos 135–144 com descrição contraditória, IDs 128 vs 130 "Kala Barítono", Promoções expiradas múltiplas nos IDs 93, 96 e 99, Pedido 8 atrasado)
- [ ] Como auditar pelo log; links para as 5 conversas de exemplo
- [ ] Limitações conhecidas e próximos passos (incluindo contador de Verificação do pedido zerado ao recarregar a página e ausência de métrica/alerta); uso de assistentes de código no desenvolvimento
