# 13 — Página de exemplo da loja com a Lia ao lado

**What to build:** quem sobe o projeto abre `/` e vê uma página de exemplo da Empório da Música, estática e sem lógica de loja, com a Lia funcionando de verdade num card à direita. O card embute o chat Chainlit, servido na mesma origem em `/lia`. Os botões "Conversar com a Lia" e "Onde está meu pedido?" e os cards "Experimente perguntar" só levam o cursor ao campo de pergunta da Lia. No mobile, eles rolam até o card antes de dar o foco. `/lia` continua abrindo o chat em tela cheia.

**Blocked by:** 10 — Chat com identidade visual da loja

**Status:** done — c7e5e87

**Executor:** builder — servidor FastAPI fino + limpeza do HTML.

**Gates:** UI (browser no caminho crítico: desktop e mobile, foco/teclado a partir dos botões da página, `/lia` em tela cheia sem regressão do ticket 10). Contratos: o comando do container muda (`chainlit run` → `uvicorn`); Dockerfile, compose e README ficam consistentes. Ordem de execução: 11 de 13 (10 → 13 → 11 → 12).

## Decisões (sessão de 2026-11-01)

- **Servidor:** FastAPI com `chainlit.utils.mount_chainlit(app, target="src/emporio/chat.py", path="/lia")`; `GET /` devolve o HTML. Um processo e uma porta (8000). A mesma origem permite o foco por JS no iframe. Sem ADR: reverter é voltar a `chainlit run`.
- **Embed:** `<iframe src="/lia">` ocupa o card inteiro com o header do próprio Chainlit. O aviso "A Lia é uma assistente virtual e pode cometer erros..." fica abaixo do iframe. Sai o header, as mensagens, o input e todo o `<script>` de respostas falsas do mock.
- **Foco:** `frame.contentDocument.getElementById('chat-input').focus()` (o Chainlit 2.12 usa esse id), precedido de `scrollIntoView` no card. Sem `postMessage` e sem `@cl.on_window_message`: os botões não enviam mensagens.
- **HTML:** mover `docs/design/emporio-da-musica.html` para `src/emporio/static/index.html` (o original não está versionado). Não manter cópia em `docs/design/`.
- **Conteúdo removido por conflito com o domínio/PRD:** chip "Acessórios" (a loja não vende Acessório), links "Entrar" e "Favoritos" (login fora de escopo) e a busca do cabeçalho (não há catálogo navegável). O texto "atendente virtual" fica como copy de marketing da página; o glossário segue com **Assistente**.
- **Mobile:** o card deixa a altura fixa de 860px e passa a `80vh` quando o layout quebra para uma coluna.

## Critérios de aceite

- [x] `GET /` devolve a página e `/lia` abre o chat Chainlit em tela cheia, com tema, logo, boas-vindas e atalhos do ticket 10 funcionando sob o root path `/lia` (conferir `custom_css`, `logo_file_url` e `default_avatar_file_url` em `/public/...`)
- [x] O card da direita embute `/lia` por iframe; a conversa funciona dentro dele (websocket sob `/lia`)
- [x] "Conversar com a Lia", "Onde está meu pedido?" e os 4 cards "Experimente perguntar" focam o `#chat-input` do iframe; no mobile rolam até o card antes
- [x] HTML sem `<script>` de respostas falsas, sem "Acessórios", sem Entrar/Favoritos e sem busca
- [x] Dockerfile/compose sobem com `uvicorn` na porta 8000; `docker compose up` serve `/` e `/lia`
- [x] Teste: `GET /` → 200 com o iframe apontando para `/lia` (TestClient, sem rede/LLM)
- [x] Verificação manual no browser: desktop e mobile, foco a partir de cada botão, conversa dentro do iframe, `/lia` em tela cheia
- [x] PRD já atualizado nesta sessão (user story 69 e módulo 9); o README do ticket 12 documenta `/` e `/lia`

## Comments

### Implementação (2026-11-01)

- Criados `src/emporio/web.py` (FastAPI: `GET /` com `FileResponse`, depois `mount_chainlit(..., path="/lia")`; caminhos derivados de `__file__`), `src/emporio/static/index.html` (movido de `docs/design/`, limpo conforme as decisões; o `<nav aria-label="Conta">` ficou só com o carrinho; "acessórios" também saiu do texto "Sobre") e `tests/test_web.py`. Alterados: `Dockerfile` (CMD `uvicorn emporio.web:app`), `pyproject.toml`/`uv.lock` (`fastapi`, `uvicorn` explícitos, sem bump de versões), docstring de `chat.py`.
- Root path: `custom_css` já funcionava (o Chainlit injeta o link com o prefixo `/lia`). Quebravam `logo_file_url`/`default_avatar_file_url` (o frontend usa o valor cru como `src`) e o `url('/public/logo.svg')` do `theme.css`. Config agora usa `/lia/public/logo.svg`; o CSS usa `url('logo.svg')` (relativo ao CSS, vale montado ou standalone). Consequência: `chainlit run` standalone ainda sobe, mas sem logo/avatar (URLs com prefixo `/lia`).
- Teste: `mount_chainlit` não carrega `chat.py` no import, então `from emporio.web import app` + `TestClient` não precisa de env, banco nem LLM; sem monkeypatch.
- O HTML entra na imagem pelo `COPY src` e o `uv sync` instala o pacote não-editável com o `static/` incluso (uv_build inclui os arquivos do módulo); verificado com `docker compose up` (`/` e `/lia/` 200).

**Verificação no browser (2026-11-01):** Playwright/Chromium em 1440×900 e 390×844. Ok:
- "Conversar com a Lia", "Consultar com a Lia" e os 4 cards levam o foco ao `#chat-input` dentro do iframe; no mobile, rolam até o card antes.
- Mensagem e "Lia está pensando..." funcionam dentro do iframe (websocket em `/lia`).
- `/lia` em tela cheia sem regressão do ticket 10.
- Zero erros de console.

Ajustes feitos depois da verificação: saiu o aviso duplicado da página (o Chainlit já mostra o próprio aviso, o que é um desvio consciente da decisão original) e "Áudio" foi trocado por "Ukuleles" na nav.

**Revisão (2026-11-01): APROVADO COM RESSALVAS.** Pendências e riscos aceitos:
- `chainlit run` sozinho fica sem logo e avatar, por causa do prefixo `/lia` no config. Está documentado na docstring de `chat.py`; o README fica para o ticket 12.
- Não há `frame-ancestors`/`X-Frame-Options`. Não é regressão (o Chainlit sozinho já era assim) e o risco é baixo, porque não há login nem ação sensível sem a Verificação do pedido.

