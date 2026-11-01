# 10 — Chat com identidade visual da loja

**What to build:** o Cliente abre o chat e vê nome, logo e cores da Empório da Música, é recebido pela Lia com uma saudação acolhedora e encontra 4 atalhos ("Procurar instrumento", "Status do pedido", "Trocas e devoluções", "Horário e endereço"). Enquanto a Lia pensa, aparece um indicador de carregamento; se algo der errado, uma mensagem amigável.

**Blocked by:** 02 — Lia responde no chat buscando Produtos

**Status:** ready-for-agent

**Executor:** builder — tema e atalhos do Chainlit.

**Gates:** UI (browser no caminho crítico: desktop e mobile, foco/teclado, estados loading e erro). Ordem de execução: 10 de 12.

- [ ] Tema Chainlit com nome, logo e cores da loja
- [ ] Mensagem de boas-vindas da Lia ao abrir a Sessão
- [ ] 4 atalhos iniciais que disparam a conversa correspondente
- [ ] Indicador de carregamento durante a resposta; estado de erro amigável
- [ ] Verificação manual no browser: desktop e mobile, foco/teclado nos atalhos, estados loading e erro (com o LLM indisponível)

## Comments

**Da revisão do ticket 07 (2026-11-01):** `src/emporio/chat.py:72` tem um `# type: ignore[no-untyped-call]` na fronteira com o Chainlit, que não publica tipos. Como este ticket mexe em `chat.py`, avaliar trocar por um wrapper tipado ou um stub local.
