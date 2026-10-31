---
status: Aceito
date: 2026-10-31
---

# 0001 — Portas do Assistente: loop explícito, contexto de ferramenta e sink de eventos

## Contexto

O **Assistente** precisa conversar com um LLM externo trocável por configuração, executar ferramentas da Loja, manter estado por **Sessão** (histórico e tentativas de **Verificação do pedido**) e emitir eventos de auditoria — tudo testável sem rede e sem chave. Frameworks de agente (LangChain, LlamaIndex, MCP) esconderiam exatamente o que queremos mostrar e testar: a decisão "consultar dados × aplicar políticas".

## Decisão

- Loop de tool calling explícito, escrito à mão, sobre três portas injetadas no `Assistant`:
  - **`LLMClient`** (Protocol): `complete(messages, tools) -> LLMResponse`, no formato de mensagens/ferramentas OpenAI. Produção usa LiteLLM com `LLM_MODEL`; testes usam um LLM falso roteirizado.
  - **`ToolRegistry`**: cada ferramenta é registrada com nome, JSON Schema dos argumentos e um handler `(args, ctx)`. Novas ferramentas entram sem mexer no loop.
  - **`EventSink`**: recebe eventos do loop (mensagem do Cliente, chamada de LLM, chamada de ferramenta, resposta final, erro). Implementação padrão no-op; o log JSONL é outra implementação.
- **`ToolContext`** (`ctx`) carrega `session`, `now` (Data de referência) e `events`. A Sessão **nunca** é argumento enviado pelo modelo — vem sempre do contexto.
- O loop executa **todos** os `tool_calls` de um turno do modelo (o Claude pede chamadas paralelas) e devolve cada resultado como mensagem `role: tool` com o `tool_call_id` correspondente antes de chamar o modelo de novo. O limite de iterações conta rodadas do modelo, não ferramentas.
- `Assistant.reply(session, message)` é síncrono; o Chainlit o chama via `cl.make_async`.

## Consequências

- Os tickets 06, 08 e 09 plugam no loop pelo `ToolContext` e pelo `EventSink` sem reescrevê-lo; por isso o ticket 02 cria essas portas desde o início.
- Trocar de provedor é configuração; trocar de framework seria reescrever só o adaptador.
- Rejeitado: servidor MCP (as ferramentas ficam isoladas, prontas para virar MCP depois) e `acompletion` assíncrono (complexidade sem ganho com um Cliente por Sessão).
