# 12 — README do projeto

**What to build:** quem chega ao repositório abre o README em português e entende como rodar o projeto (Docker e local), como trocar o provedor de LLM, por que cada escolha técnica foi feita, quais suposições foram tomadas sobre os dados e o manual, como auditar pelo log, as limitações conhecidas e como assistentes de código foram usados.

**Blocked by:** 10 — Chat com identidade visual da loja; 11 — Gerador de conversas de exemplo + as 5 conversas; 13 — Página de exemplo da loja com a Lia

**Status:** ready-for-agent

**Executor:** builder — documentação com justificativas, não mecânica.

**Gates:** nenhum gate de superfície. Ordem de execução: 13 de 13. ADRs: 0001–0005 (referenciados).

- [ ] Como rodar: Docker (`cp .env.example .env`, informar a chave, comando único) e local com `uv`; testes sem chave/rede
- [ ] Rotas: `/` (página de exemplo da loja, estática, com a Lia no card à direita) e `/lia` (chat em tela cheia)
- [ ] Configuração: `LLM_MODEL`, chaves por provedor, `AGENT_NOW`, `DB_PATH`
- [ ] Decisões justificadas, com links para os ADRs: LiteLLM + loop explícito em vez de framework/MCP; Manual inteiro no contexto em vez de RAG (com limiar em que RAG passaria a valer); ferramentas fixas em vez de agente SQL; SQLite; Chainlit; prazos de pós-venda em código
- [ ] Tratamento de dados e suposições: contradições do manual resolvidas (incluindo troca por defeito contada da compra, "Black Friday em todo o catálogo", "mais de 300 instrumentos"); divergências preservadas (Pedidos 3 e 20, PIX sem 5% nos Pedidos, `coming_soon` em Pedido entregue, categorias vazias, e-mail duplicado, Produtos 135–144 com descrição contraditória, IDs 128 vs 130 "Kala Barítono", Promoções expiradas múltiplas nos IDs 93, 96 e 99, Pedido 8 atrasado)
- [ ] Como auditar pelo log; links para as 5 conversas de exemplo
- [ ] Limitações conhecidas e próximos passos (incluindo contador de Verificação do pedido zerado ao recarregar a página e ausência de métrica/alerta); uso de assistentes de código no desenvolvimento

## Comments

**Da revisão do ticket 05 (2026-11-01):** registrar nas suposições: WhatsApp (67) 3321-4500 da seção 7 unificado em (67) 3341-4444; "mais de 300 instrumentos" e "Sugerir lojas parceiras quando possível" (7.1) removidos do Manual em Markdown. Registrar nas limitações: com `LLM_MODEL=gemini/*`, o LiteLLM traduz `cache_control` em context caching, que exige um mínimo de tokens; esse caminho não foi verificado. Com OpenAI, o `cache_control` é descartado pelo LiteLLM.

**Da revisão do ticket 06 (2026-11-01):** registrar nas suposições que os Itens do pedido saem sem preço unitário, porque `order_items` não o grava, e que usar o preço atual do catálogo recalcularia o Pedido. Registrar nas limitações:
- o e-mail duplicado (Clientes 11 e 43) libera o Pedido 10 para quem controla aquela caixa;
- os casos negados fazem quantidades diferentes de consultas, o que só aparece no `duration_ms` do log de auditoria;
- o bloqueio começa na 4ª tentativa, como diz o ADR-0003, o que custa ao Cliente uma volta a mais.

**Do teste manual do ticket 06 (2026-11-01):** o README deve dizer que, depois de atualizar o código ou o `.env`, é preciso rodar `docker compose up --build`. Sem `--build` o container antigo continua rodando a versão anterior: no teste, a Lia do ticket 02 recusou consultar Pedidos.

**Da revisão do ticket 08 (2026-11-01):** registrar nas Limitações do log de auditoria:
- as respostas da Lia (`final_response`) contêm o primeiro nome do Cliente verificado e, em Reclamações, o nome informado;
- nomes digitados em texto livre não são mascarados;
- e-mails e telefones são mascarados em todo o log, e o telefone público da loja é preservado;
- no Linux, `./logs` criado pelo Docker como root impede a escrita; contorno: `mkdir -p logs && sudo chown 10001 logs`;
- não há métrica nem alerta: o JSONL é a trilha de auditoria (ADR-0004).
- números estrangeiros não são mascarados;
- telefone colado a palavra que já contém dígito (`pedido7fone6799…`) não é mascarado;
- o telefone público da loja só é preservado com DDD 67 ou sem DDD;
- em texto livre, alguns códigos são mascarados a mais (`YMH12345678`), porque mascarar a mais é falha segura.
