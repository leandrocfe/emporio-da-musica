# 02 — Lia responde no chat buscando Produtos (tracer bullet ponta a ponta)

**What to build:** o desenvolvedor roda `docker compose up`, abre o chat na porta 8000, escreve "tem violão Yamaha?" e a Lia responde listando Produtos do catálogo real. Por baixo: o Assistente (`Assistant.reply(session, message)`) roda um loop explícito de tool calling — envia histórico + definições de ferramentas ao modelo, executa a ferramenta pedida (`search_products`), devolve o resultado, repete até a resposta final. O modelo de linguagem é dependência injetada; a implementação de produção usa LiteLLM com `LLM_MODEL` (padrão `anthropic/claude-sonnet-5-5`). System prompt mínimo com a persona Lia (refinado no ticket 05). UI Chainlit básica com histórico em memória por Sessão do navegador.

**Blocked by:** 01 — Scaffold do projeto e busca textual no catálogo

**Status:** done — a2889d9

**Executor:** architect — cross-layer (LLM externo, portas, registro de ferramentas, Chainlit, Docker) e contratos consumidos por 04–09.

**Gates:** Assíncrono/integrações (LLM externo: timeout, logging seguro); Contratos (portas do Assistente, formato de ferramentas); UI (mínima: chat responde no browser). Ordem de execução: 02 de 12. ADRs: 0001, 0004.

- [x] `Assistant.reply(session, message)` retorna a resposta final da Lia; histórico mantido entre mensagens da mesma Sessão
- [x] Registro de ferramentas extensível (as próximas ferramentas entram sem mexer no loop)
- [x] Handlers de ferramenta recebem `(args, ctx)`; `ctx` traz `session`, `now` e `events`; a Sessão nunca é argumento do modelo
- [x] `EventSink` com implementação no-op padrão
- [x] Todos os `tool_calls` de um turno são executados e respondidos com `tool_call_id` antes da próxima chamada ao modelo
- [x] Adaptador LiteLLM no formato de mensagens/ferramentas OpenAI; provedor trocável só por `LLM_MODEL`; só a chave do provedor em uso é obrigatória
- [x] Chainlit como adaptador fino sobre o Assistente (chamado via `cl.make_async`); ferramentas não aparecem para o Cliente
- [x] `docker compose up` sobe o chat na porta 8000 a partir de `.env` (com `.env.example` versionado, que documenta `cp .env.example .env`); banco SQLite em volume
- [x] Testes com LLM falso roteirizado: ferramenta pedida é executada com os argumentos do modelo e o resultado volta ao modelo; duas chamadas de ferramenta no mesmo turno; resposta final retornada; histórico mantido
- [x] Smoke test manual confirma o ID do modelo em `LLM_MODEL` contra o provedor real
- [x] Verificação manual: pergunta real no browser retorna Produtos do catálogo

## Comments

**Herdado do ticket 01 (revisão):**
- Caminho padrão de dados assume instalação editable; no Docker, definir `DATA_DIR` e `DB_PATH` explicitamente.
- Não montar o volume do banco sobre o diretório dos CSVs (esconderia os dados); banco em diretório próprio.
- Query só com pontuação vira zero tokens e devolve o catálogo inteiro — decidir na camada de ferramenta (exigir ao menos um filtro ou aceitar).
- Busca exige todos os tokens (AND): instruir o modelo a enviar só palavras-chave (sem "com", "para", "de"), ou adicionar stopwords.
- Validação de tipos dos argumentos (`limit` não-int) fica na camada de ferramentas.

**Smoke test real (2026-10-31):** `anthropic/claude-sonnet-5-5` aceito pelo provedor via `docker compose up --build`. "tem violão Yamaha?" → 5 Yamaha da categoria Violões com Preço de tabela correto; "e o mais barato?" → C40 R$ 599,90 usando o histórico da Sessão. Achados registrados nos tickets 03 (ordenação) e 05 (informar total).
