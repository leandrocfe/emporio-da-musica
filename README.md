# Lia, assistente de atendimento da Empório da Música

A Lia é a assistente virtual da Empório da Música, loja de instrumentos musicais de Campo Grande/MS. Ela atende o Cliente por chat em português: busca Produtos no catálogo com preço e Disponibilidade corretos, consulta Pedidos depois da Verificação do pedido, responde dúvidas do Manual de políticas, registra Reclamações com Protocolo e recusa com gentileza o que é Fora de escopo (inclusive Acessórios, que a loja não vende).

![Página de exemplo da loja com a Lia](screenshots/emporio-da-musica.png)

O vocabulário do domínio (Produto, Pedido, Verificação do pedido, Entrega prevista etc.) está em [`CONTEXT.md`](CONTEXT.md) e é usado com o mesmo sentido neste documento. O escopo completo está no [PRD](docs/PRD.md). Documentação em português, código em inglês.

## Sumário

- [Como rodar](#como-rodar)
- [Rotas](#rotas)
- [Configuração](#configuração)
- [Arquitetura em uma página](#arquitetura-em-uma-página)
- [Decisões técnicas](#decisões-técnicas)
- [Dados e suposições](#dados-e-suposições)
- [Como auditar pelo log](#como-auditar-pelo-log)
- [Conversas de exemplo](#conversas-de-exemplo)
- [Uso de assistentes de código](#uso-de-assistentes-de-código)

## Como rodar

### Docker (recomendado)

```bash
cp .env.example .env
# edite o .env e preencha ANTHROPIC_API_KEY (ou a chave do provedor escolhido em LLM_MODEL)
docker compose up --build
```

Depois abra <http://localhost:8000>. O container semeia o banco SQLite a partir dos CSVs de `data/` antes de aceitar conexões (se o seed falhar, o container para).

Depois de **qualquer mudança no código ou no `.env`**, rode de novo `docker compose up --build`. Sem `--build`, o container continua rodando a versão anterior.

O banco fica no volume `emporio-db`; o log de auditoria fica em `./logs/audit.jsonl` no host. As Reclamações vivem nesse banco e sobrevivem a reinícios (ver [ADR-0002](docs/adr/0002-persistencia-sqlite-e-dinheiro.md)).

No Linux, se o Docker criar `./logs` como root, a escrita do log falha (o chat continua funcionando e o container avisa no stderr). Contorno:

```bash
mkdir -p logs && sudo chown 10001 logs
```

### Local, com `uv`

Requer Python 3.13 e [`uv`](https://docs.astral.sh/uv/).

```bash
cp .env.example .env            # preencha a chave do provedor
uv sync
uv run --env-file .env python -m emporio.seed          # cria data/emporio.db a partir dos CSVs
uv run --env-file .env uvicorn emporio.web:app --port 8000
```

O seed recria as tabelas de catálogo e preserva as Reclamações. Rode-o de novo sempre que trocar os CSVs.

### Testes e verificações

Os testes não precisam de chave de API nem de rede (o LLM é substituído por um roteiro falso):

```bash
uv run pytest
uv run ruff check .
uv run mypy
```

## Rotas

| Rota | O que é |
|---|---|
| `/` | Página de exemplo da loja: HTML estático, sem lógica de loja, com a Lia num card à direita (iframe). Os botões da página só levam o cursor ao campo de pergunta da Lia. |
| `/lia` | O chat (Chainlit) em tela cheia. |

As duas rotas são servidas por um FastAPI fino (`src/emporio/web.py`) que monta o Chainlit em `/lia`, na mesma origem, na porta 8000.

## Configuração

Tudo por variáveis de ambiente, lidas do `.env` (Docker) ou de `uv run --env-file .env` (local). O `.env` nunca é versionado.

| Variável | Para quê | Padrão |
|---|---|---|
| `LLM_MODEL` | Modelo no formato LiteLLM `provedor/modelo`. | `anthropic/claude-sonnet-5-5` |
| `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY` | Chave do provedor de `LLM_MODEL`. Só a do provedor em uso é obrigatória. | vazio |
| `LLM_TIMEOUT_SECONDS` | Timeout de cada chamada ao modelo. | `30` |
| `AGENT_NOW` | Fixa a Data de referência (ISO 8601; sem offset vale `America/Campo_Grande`). Vazio usa o relógio real. Um valor inválido derruba a aplicação na partida, com mensagem clara. | vazio |
| `DB_PATH` | Arquivo SQLite. | `data/emporio.db` (local); `/app/var/emporio.db` (Docker) |
| `DATA_DIR` | Pasta dos CSVs. | `data/` (local); `/app/data` (Docker) |
| `LOG_PATH` / `LOG_DIR` | Arquivo do log de auditoria. `LOG_PATH` tem precedência; `LOG_DIR` usa `audit.jsonl` dentro dela. | `logs/audit.jsonl` (local); `/app/logs/audit.jsonl` (Docker) |

No Docker, `DATA_DIR`, `DB_PATH` e `LOG_PATH` são fixados no `docker-compose.yml`, de modo que um valor perdido no `.env` não aponte o banco para os CSVs.

**Trocar de provedor** é só mudar `LLM_MODEL` e preencher a chave correspondente. Exemplos do `.env.example`:

```bash
LLM_MODEL=gemini/gemini-3-flash-preview   # + GEMINI_API_KEY
LLM_MODEL=openai/gpt-5-mini               # + OPENAI_API_KEY
```

O provedor padrão é o Claude; também é possível usar Gemini ou OpenAI trocando só a configuração acima.

## Arquitetura em uma página

```
Navegador ── / (página estática) ── iframe ──► /lia (Chainlit)
                                                  │  uma Sessão por aba (em memória)
                                                  ▼
                                      Assistant.reply(session, mensagem)
                       loop de tool calling explícito (máx. 5 rodadas do modelo)
                          │                 │                    │
                      LLMClient        ToolRegistry          EventSink
                    (LiteLLM, ADR-1)  search_products        (log JSONL
                                      get_product             mascarado)
                                      get_order
                                      register_complaint
                                          │
                                  StoreService / SQLite
```

- O prompt de sistema tem um prefixo estático (persona, regras, categorias, Manual de políticas inteiro) e, depois do breakpoint de cache, um bloco dinâmico com Data de referência, dia da semana e situação da loja (aberta/fechada), calculados em código.
- Preço, Disponibilidade, Verificação do pedido e prazos de pós-venda são regras em código (`StoreService`), nunca do prompt. O modelo decide **quando** chamar uma ferramenta; o **resultado** vem pronto.
- Falhas do provedor (timeout, 429, 5xx) têm até 2 retentativas com backoff; ao final, o Cliente recebe uma mensagem amigável e o erro vai para o log. O histórico é truncado em fronteira de mensagem do Cliente ([ADR-0004](docs/adr/0004-prompt-caching-truncamento-e-retry.md)).

## Decisões técnicas

### LiteLLM + loop de tool calling explícito, em vez de framework de agente ou MCP

O loop é escrito à mão sobre três portas injetadas (`LLMClient`, `ToolRegistry`, `EventSink`). A decisão que importa aqui, consultar dados ou aplicar política, fica visível e testável, sem esconder o fluxo atrás de um framework. O LiteLLM dá um formato único (OpenAI) para vários provedores, então trocar de provedor é configuração. Os testes usam um LLM falso roteirizado e rodam sem rede. As ferramentas ficam isoladas em módulo próprio, prontas para virar um servidor MCP, mas MCP não foi adotado: seria infraestrutura sem ganho com um Cliente por Sessão. Detalhes e alternativas rejeitadas em [ADR-0001](docs/adr/0001-portas-do-assistente.md).

### Manual de políticas inteiro no contexto, em vez de RAG

O Manual tem cerca de 1,8 mil palavras; o prompt completo gira em torno de 6 mil tokens por chamada (medido no log de auditoria com Gemini; o tokenizador de cada provedor conta diferente). Cabe com folga, nenhuma busca pode "esquecer" uma regra e o prefixo estático é cacheável. RAG só passa a valer quando o Manual deixar de caber confortavelmente no contexto, ou quando o custo por mensagem, mesmo com cache, ficar relevante. Até lá, recuperação a mais seria só mais uma fonte de erro. O bloco dinâmico fica depois do breakpoint de cache, então mudar a hora não invalida o cache do Manual. Ver [ADR-0004](docs/adr/0004-prompt-caching-truncamento-e-retry.md).

### Ferramentas fixas, em vez de agente SQL

O modelo chama quatro ferramentas com argumentos tipados (`search_products`, `get_product`, `get_order`, `register_complaint`). Não existe SQL gerado pelo LLM: as consultas são parametrizadas e as regras de preço, Disponibilidade e Verificação do pedido ficam em código determinístico. Um agente SQL poderia expor dados de outros Clientes e errar cálculo de preço. Ver o [PRD](docs/PRD.md) (seção "Módulos") e [ADR-0003](docs/adr/0003-verificacao-do-pedido.md) para a Verificação do pedido, que é decidida em código (resposta genérica idêntica para Pedido inexistente e contato errado, bloqueio na 4ª tentativa).

### SQLite

Um arquivo, sem serviço externo, suficiente para 65 Produtos e 20 Pedidos. O seed recria o catálogo a partir dos CSVs a cada inicialização (os CSVs são a fonte de verdade) e preserva a tabela de Reclamações, que é o único estado durável. Dinheiro é guardado em centavos inteiros, com `ROUND_HALF_UP` (Yamaha C40, ID 81: PIX de R$ 569,91, e não 569,90). Ver [ADR-0002](docs/adr/0002-persistencia-sqlite-e-dinheiro.md).

### Chainlit

Dá um chat web com histórico, indicador de carregamento, atalhos e tema da loja sem escrever front-end, e deixa o adaptador de UI fino: a lógica está no `Assistant`, então outra UI (ou uma API HTTP) reaproveitaria o núcleo. Não há ADR próprio; a escolha está no [PRD](docs/PRD.md).

### Prazos de pós-venda calculados em código

Arrependimento (7 dias corridos da Entrega prevista), troca por defeito (30 dias corridos da data do Pedido) e garantia legal (90 dias corridos da Entrega prevista) são calculados pelo `get_order` com a Data de referência. Aritmética de datas feita pelo modelo contradiz a regra de nunca inventar prazo. Como a Entrega prevista é uma aproximação (os dados não têm a data real de entrega), as janelas contadas dela trazem `borderline` (até 2 dias antes ou depois do limite) e Pedido enviado com a Entrega prevista vencida vem com `overdue`; nesses casos a Lia encaminha ao Atendimento humano em vez de negar um direito. Ver [ADR-0005](docs/adr/0005-prazos-de-pos-venda-em-codigo.md).

## Dados e suposições

Os CSVs em `data/` são a fonte de verdade e não foram corrigidos. O Manual de políticas foi convertido uma vez do PDF original ([`docs/politicas-da-loja.pdf`](docs/politicas-da-loja.pdf)) para Markdown revisado à mão e versionado em [`src/emporio/politicas-da-loja.md`](src/emporio/politicas-da-loja.md); é esse arquivo que entra no prompt.

### Contradições do Manual e como foram resolvidas

- **Telefone/WhatsApp:** o PDF traz (67) 3341-4444 e, na seção 7, (67) 3321-4500. Foi unificado em **(67) 3341-4444**.
- **E-mail:** `contato@emporiodamusica.com.br`, sem o acento que aparece por erro de digitação.
- **Parcelamento:** valem as faixas da seção 3.1: até 3x com parcela mínima de R$ 50, 4x a 6x com R$ 80, 7x a 12x com R$ 100.
- **Troca por defeito:** conta 30 dias da **compra** (seção 4.2), não do recebimento. Arrependimento e garantia legal contam do recebimento, aproximado pela Entrega prevista ([ADR-0005](docs/adr/0005-prazos-de-pos-venda-em-codigo.md)).
- **"Mais de 300 instrumentos":** frase removida do Manual em Markdown. O catálogo tem 65 Produtos (2 descontinuados, fora da busca). Quando uma busca não retorna nada (por exemplo, saxofone), a Lia orienta consultar a loja pelo telefone em vez de afirmar que a loja não trabalha com aquilo.
- **"Sugerir lojas parceiras quando possível" (seção 7.1):** removido; não há lojas parceiras nos dados, e a Lia não inventa indicações para Acessórios.
- **"Black Friday em todo o catálogo":** só a Promoção vigente registrada no sistema é oferecida ao Cliente.

### Divergências nos dados, preservadas

- **Pedidos 3 e 20:** o `total_brl` gravado (R$ 3.450 e R$ 1.400) difere da soma dos preços atuais dos itens (R$ 3.498 e R$ 1.488). O Valor do pedido é o que está gravado e nunca é recalculado.
- **PIX sem 5% nos Pedidos:** Pedidos pagos no PIX têm o valor do Preço de tabela (por exemplo, Pedido 1 = R$ 11.499, o preço do Produto 93). A regra dos 5% vale para o catálogo, não retroage aos Pedidos.
- **`coming_soon` em Pedido entregue:** o Pedido 3 (entregue) contém o Produto 130, hoje Em breve.
- **Categorias vazias:** Instrumentos de Sopro (Madeiras), Instrumentos de Sopro (Metais) e Cordas Orquestrais não têm Produtos.
- **E-mail duplicado:** os Clientes 11 e 43 compartilham `bruno.martins@jmail.com`. A Verificação do pedido é por Pedido, então cada um só enxerga o próprio Pedido.
- **Produtos 135–144:** a descrição contradiz o nome ou as specs (por exemplo, o 135, "Music Man Bass 1X", é descrito como Fender Jazz Bass). Isso afeta a busca pela descrição.
- **IDs 128 e 130:** dois "Kala Barítono" distintos (128 ativo, 130 Em breve). `get_product` com esse nome devolve `ambiguous` e a Lia pergunta qual.
- **Promoções expiradas múltiplas:** os Produtos 93, 96 e 99 têm mais de uma Promoção expirada. Todas são expostas ao modelo no `get_product`, para a Lia poder dizer que "essa promoção não está mais vigente", e nenhuma é prometida.
- **Pedido 8:** enviado, com Entrega prevista em 2026-02-28. Com Data de referência posterior a isso, aparece como `overdue` e a Lia encaminha ao Atendimento humano.

### Outras suposições

- **Itens do pedido sem preço unitário:** `order_items` não grava o preço pago. Usar o preço atual do catálogo recalcularia o Pedido, o que é proibido; por isso os Itens saem só com Produto e quantidade.
- **Preço:** com Promoção vigente, mostra Preço de tabela, percentual e Preço promocional, sem PIX (promoções não são cumulativas). Sem promoção, Preço de tabela e Preço no PIX (5%). Com mais de uma Promoção vigente, vale a maior.
- **Disponibilidade:** o estoque exato nunca é exposto. 0 é esgotado, 1 a 3 são últimas unidades.
- **Horário:** seg–sex 09:00–18:00, sáb 09:00–13:00, domingo e feriados fechado (nacionais, estadual de MS e municipais de Campo Grande, calculados em código).
- **Data de referência:** relógio real em `America/Campo_Grande`; `AGENT_NOW` fixa o "agora" para demonstrações reproduzíveis. As conversas de exemplo usam `2026-03-23T10:00:00-04:00`, logo após o último Pedido do conjunto.

## Como auditar pelo log

Cada evento do `Assistant` vira uma linha JSON (JSON Lines) em `logs/audit.jsonl` (no Docker, `./logs/audit.jsonl` no host; configurável por `LOG_PATH` ou `LOG_DIR`). Toda linha tem `ts` (ISO 8601 com offset), `session_id` e `type`:

| `type` | O que registra |
|---|---|
| `customer_message` | Texto da mensagem do Cliente. |
| `llm_call` | Rodada, modelo, `latency_ms`, tokens (a partir de `usage`), tokens de cache, `prompt_hash`/`prompt_version` (o prompt de sistema vai por hash, não inteiro) e as ferramentas pedidas. |
| `tool_call` | `name`, `arguments`, `ok`, `duration_ms` e `result`. Resultados longos (acima de 2.000 caracteres) viram `{"truncated": true, "chars": N, "preview": ...}`. |
| `final_response` | A resposta da Lia. |
| `error` | `error_type` e `message` de falhas do provedor ou do loop. |

Para ver tudo o que uma conversa fez, filtre por `session_id`:

```bash
grep '"session_id": "<id>"' logs/audit.jsonl
```

Para ver quais ferramentas a Lia escolheu para cada pergunta, filtre `"type": "tool_call"`.

**Mascaramento** (`src/emporio/masking.py`), aplicado antes da escrita, em todo o conteúdo:

- e-mail: `joao@gmail.com` vira `j***@g***.com`;
- telefone: todos os dígitos viram `*`, menos os dois últimos (`+55 (67) 99789-0123` vira `+** (**) *****-**23`);
- valores sob chaves que carregam dado pessoal (como o primeiro nome do Cliente em `get_order` e o `name` de `register_complaint`) viram `***`;
- o telefone público da loja, (67) 3341-4444, é preservado, porque é o fallback que a Lia dá ao Cliente.

A falha de escrita do log nunca derruba a resposta ao Cliente: o erro vai uma vez para o stderr por sequência de falhas.

## Conversas de exemplo

Cinco conversas reais com o modelo, com a Data de referência fixa em 2026-03-23 e o trecho correspondente do log de auditoria (já mascarado). Índice em [`docs/conversas/README.md`](docs/conversas/README.md):

1. [Violões até R$ 1000: busca, PIX e produto esgotado](docs/conversas/01-violoes-ate-mil-reais.md)
2. [Takamine GD20 e uma Promoção expirada](docs/conversas/02-takamine-gd20-promocao-expirada.md)
3. [Devolução do Pedido 7 com Verificação do pedido](docs/conversas/03-devolucao-pedido-7.md)
4. [Acessórios e uma pergunta fora de escopo](docs/conversas/04-acessorios-e-fora-de-escopo.md)
5. [Reclamação registrada com Protocolo](docs/conversas/05-reclamacao-com-protocolo.md)

Para regenerá-las contra o modelo configurado (usa a chave do `.env` e a rede):

```bash
uv run --env-file .env python -m emporio.examples
```

O gerador roda cada roteiro numa Sessão nova e num banco recém-semeado, com temperatura 0. Os arquivos só são escritos se todas as conversas terminarem sem erro do provedor.

## Uso de assistentes de código

O projeto foi desenvolvido com o Claude Code, usando um conjunto de agentes com papéis separados:

- **Planejamento:** o escopo virou um [PRD](docs/PRD.md), [ADRs](docs/adr/) e um glossário ([`CONTEXT.md`](CONTEXT.md)), e depois tickets em `.scratch/atendimento-lia/`. Um agente arquiteto analisou PRD e tickets antes de qualquer execução.
- **Implementação:** agentes executores (por complexidade) implementaram cada ticket, com testes nos pontos combinados no ticket.
- **Revisão independente:** cada ticket concluído foi revisado por um agente revisor separado, com contexto limpo, que reporta achados sem corrigir; a correção volta ao executor. Tickets críticos (como a Verificação do pedido) tiveram revisão por um modelo distinto.
- **Humano:** os commits e os testes manuais no navegador são feitos pelo mantenedor, assim como a geração e a revisão das conversas de exemplo.
