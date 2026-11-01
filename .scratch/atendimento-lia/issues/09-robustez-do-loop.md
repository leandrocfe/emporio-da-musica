# 09 — Robustez do loop do Assistente

**What to build:** a conversa nunca quebra para o Cliente. Se o modelo entra em loop de ferramentas, pede ferramenta inexistente, manda argumentos inválidos ou o provedor falha, a Lia se recupera ou responde com uma mensagem amigável sugerindo tentar de novo ou falar com a loja.

**Blocked by:** 02 — Lia responde no chat buscando Produtos

**Status:** done — d150db8

**Executor:** builder — política definida no ADR-0004; seams com LLM falso.

**Gates:** Assíncrono/integrações (timeout, retry, idempotência, evento de erro). Ordem de execução: 09 de 12. ADRs: 0001, 0004.

- [x] Limite de iterações de ferramenta por mensagem (ex.: 5 rodadas do modelo); ao estourar, resposta de fallback amigável
- [x] Timeout e até 2 retentativas com backoff na chamada ao LLM, só em timeout, 429 e 5xx (nunca em 400/401); `sleep` injetável; falha final vira mensagem amigável e emite evento `error` no `EventSink`
- [x] Ferramenta inexistente ou argumentos inválidos viram erro estruturado devolvido ao modelo, sem derrubar a conversa
- [x] Histórico por Sessão truncado às últimas N trocas, cortando só em fronteira de mensagem do Cliente, sem quebrar pares chamada/resultado de ferramenta
- [x] Testes com LLM falso: limite de iterações e fallback; falha do LLM 3× vira mensagem amigável + evento `error` em sink em memória; 400 não é retentado; ferramenta desconhecida e argumentos inválidos devolvidos ao modelo; truncamento sem resultado de ferramenta órfão
