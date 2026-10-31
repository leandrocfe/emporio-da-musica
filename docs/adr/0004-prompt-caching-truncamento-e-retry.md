---
status: Aceito
date: 2026-10-31
---

# 0004 — Layout do prompt, caching, truncamento de histórico e retry do LLM

## Contexto

O **Manual de políticas** vai inteiro no system prompt (milhares de tokens, mesmo conteúdo em toda chamada), enquanto a Data de referência e a situação da loja mudam a cada minuto. A Anthropic rejeita histórico que comece por mensagem `assistant`/`tool` ou que tenha `tool_use` sem `tool_result`. O LLM é uma integração externa sujeita a timeout, 429 e 5xx.

## Decisão

- **Ordem do system prompt**: prefixo estático (persona Lia, regras, lista de categorias, Manual de políticas) seguido de breakpoint `cache_control: ephemeral`; o bloco dinâmico (Data de referência, dia da semana, aberta/fechada, próxima abertura) vem **depois** do breakpoint. O `cache_control` só é enviado quando `litellm.supports_prompt_caching(model)` for verdadeiro.
- **Truncamento**: mantém as últimas N trocas, cortando sempre numa fronteira de mensagem `user`, de modo que nenhum resultado de ferramenta fique sem a chamada correspondente.
- **Retry**: timeout explícito por chamada (ex.: 30 s); até 2 retentativas com backoff apenas em timeout, 429 e 5xx — nunca em 400/401. O backoff vive no Assistente, com `sleep` injetável para teste. Repetir a chamada ao LLM é idempotente porque ferramentas já executadas não são reexecutadas.
- **Logging seguro**: e-mails e telefones mascarados antes da escrita; o system prompt é registrado por hash/versão, não por inteiro. Tokens vêm de `usage`, não de cálculo de custo (o modelo configurado pode não constar no mapa de custos do LiteLLM).
- **Métrica/alerta**: não há infraestrutura de alerta; o log JSONL com latência, tokens e erros a substitui e isso fica registrado como limitação.

## Consequências

- Mudar o bloco dinâmico não invalida o cache do Manual.
- RAG passaria a valer quando o Manual deixar de caber confortavelmente no contexto ou o custo por mensagem, mesmo com cache, ficar relevante.
