# 02 — Lia responde no chat buscando Produtos (tracer bullet ponta a ponta)

**What to build:** o desenvolvedor roda `docker compose up`, abre o chat na porta 8000, escreve "tem violão Yamaha?" e a Lia responde listando Produtos do catálogo real. Por baixo: o Assistente (`Assistant.reply(session, message)`) roda um loop explícito de tool calling — envia histórico + definições de ferramentas ao modelo, executa a ferramenta pedida (`search_products`), devolve o resultado, repete até a resposta final. O modelo de linguagem é dependência injetada; a implementação de produção usa LiteLLM com `LLM_MODEL` (padrão `anthropic/claude-sonnet-5-5`). System prompt mínimo com a persona Lia (refinado no ticket 05). UI Chainlit básica com histórico em memória por Sessão do navegador.

**Blocked by:** 01 — Scaffold do projeto e busca textual no catálogo

**Status:** ready-for-agent

**Executor:** architect — cross-layer (LLM externo, portas, registro de ferramentas, Chainlit, Docker) e contratos consumidos por 04–09.

**Gates:** Assíncrono/integrações (LLM externo: timeout, logging seguro); Contratos (portas do Assistente, formato de ferramentas); UI (mínima: chat responde no browser). Ordem de execução: 02 de 12. ADRs: 0001, 0004.

- [ ] `Assistant.reply(session, message)` retorna a resposta final da Lia; histórico mantido entre mensagens da mesma Sessão
- [ ] Registro de ferramentas extensível (as próximas ferramentas entram sem mexer no loop)
- [ ] Handlers de ferramenta recebem `(args, ctx)`; `ctx` traz `session`, `now` e `events`; a Sessão nunca é argumento do modelo
- [ ] `EventSink` com implementação no-op padrão
- [ ] Todos os `tool_calls` de um turno são executados e respondidos com `tool_call_id` antes da próxima chamada ao modelo
- [ ] Adaptador LiteLLM no formato de mensagens/ferramentas OpenAI; provedor trocável só por `LLM_MODEL`; só a chave do provedor em uso é obrigatória
- [ ] Chainlit como adaptador fino sobre o Assistente (chamado via `cl.make_async`); ferramentas não aparecem para o Cliente
- [ ] `docker compose up` sobe o chat na porta 8000 a partir de `.env` (com `.env.example` versionado, que documenta `cp .env.example .env`); banco SQLite em volume
- [ ] Testes com LLM falso roteirizado: ferramenta pedida é executada com os argumentos do modelo e o resultado volta ao modelo; duas chamadas de ferramenta no mesmo turno; resposta final retornada; histórico mantido
- [ ] Smoke test manual confirma o ID do modelo em `LLM_MODEL` contra o provedor real
- [ ] Verificação manual: pergunta real no browser retorna Produtos do catálogo
