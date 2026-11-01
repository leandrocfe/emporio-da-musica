# 10 — Chat com identidade visual da loja

**What to build:** o Cliente abre o chat e vê nome, logo e cores da Empório da Música, é recebido pela Lia com uma saudação acolhedora e encontra 4 atalhos ("Procurar instrumento", "Status do pedido", "Trocas e devoluções", "Horário e endereço"). Enquanto a Lia pensa, aparece um indicador de carregamento; se algo der errado, uma mensagem amigável.

**Blocked by:** 02 — Lia responde no chat buscando Produtos

**Status:** approved — aguardando commit

**Executor:** builder — tema e atalhos do Chainlit.

**Gates:** UI (browser no caminho crítico: desktop e mobile, foco/teclado, estados loading e erro). Ordem de execução: 10 de 13.

- [x] Tema Chainlit com nome, logo e cores da loja
- [x] Mensagem de boas-vindas da Lia ao abrir a Sessão
- [x] 4 atalhos iniciais que disparam a conversa correspondente
- [x] Indicador de carregamento durante a resposta; estado de erro amigável
- [x] Verificação manual no browser: desktop e mobile, foco/teclado nos atalhos, estados loading e erro (com o LLM indisponível)

## Comments

**Da revisão do ticket 07 (2026-11-01):** `src/emporio/chat.py:72` tem um `# type: ignore[no-untyped-call]` na fronteira com o Chainlit, que não publica tipos. Como este ticket mexe em `chat.py`, avaliar trocar por um wrapper tipado ou um stub local.


**Implementação (2026-11-01):** identidade visual original local; não representa ativos oficiais. Testes do adaptador cobrem as mensagens dos quatro atalhos e o erro amigável. A verificação manual permanece pendente: o Dia recusou foco (`window_not_focused`) mesmo após `get-app-state --restore-window`; `orca computer capabilities` informa `windows.focus=false`. Sem janela focável, permanecem pendentes desktop, mobile, teclado e estados no navegador. O servidor local respondeu HTTP 200. O `type: ignore[no-untyped-call]` permanece na fronteira Chainlit, cujos métodos `send` e `update` não são anotados.

**Revisão visual (2026-11-01):** identidade refeita a partir de `docs/design/emporio-da-musica.html`. Paleta marrom/bordô trocada por azul #2F4BFF (hover #1A33D6), tinta #0E1330 e lima #C8F25A, com fundo/superfícies claros (#F4F6FB, #E3E7F3); fonte Georgia/Avenir trocada por Plus Jakarta Sans (Google Fonts via `@import`, títulos 800). `public/logo.svg` recriado com o símbolo pin/nota e wordmark "empório da música"; o fragmento `#avatar` continua recortando só o símbolo. Balões (assistente #F4F6FB, Cliente azul), atalhos em pílula e composer redesenhados; rótulos dos atalhos inalterados. A verificação manual no browser segue pendente.

**Verificação no browser (2026-11-01):** Playwright/Chromium em 1280×820 e 390×844, com DB semeado e LLM indisponível. Ok: boas-vindas com os 4 atalhos; Tab chega aos chips com foco visível; anel de foco no composer; "Lia está pensando..." durante a resposta; erro amigável; no mobile os chips ficam empilhados. Não conferido: Safari/iOS (recorte `logo.svg#avatar`).

**Revisão (2026-11-01): APROVADO COM RESSALVAS.** Riscos aceitos:
- Seletores presos ao DOM do Chainlit 2.12 (`.bg-accent`, `.ai-message > div:last-child`). O `uv.lock` fixa a versão; rever `public/theme.css` em qualquer upgrade.
- O `@import` do Google Fonts faz uma requisição externa. Há fallback para `system-ui`, e o wordmark do SVG sempre renderiza em `system-ui`.
- O caminho de rejeição do `on_shortcut` (payload inválido) não tem teste.

