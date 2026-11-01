# 01 — Scaffold do projeto e busca textual no catálogo

**What to build:** o projeto Python existe, instala com `uv` e roda a suíte de testes. Ao inicializar, o seed cria o schema completo e recria todas as tabelas de catálogo a partir dos CSVs (fonte de verdade), preservando as Reclamações. A Loja (`StoreService`) responde `search_products` por texto: "violao yamaha" encontra "Violão Yamaha…" mesmo sem acento, devolve o total encontrado e no máximo `limit` Produtos (padrão 5, teto 10), exclui Produtos descontinuados e mostra o Preço de tabela. Preços promocionais e Disponibilidade ficam para o ticket 03.

**Blocked by:** Nenhum — pode começar imediatamente.

**Status:** ready-for-agent

**Executor:** architect — define schema, representação de dinheiro, layout do projeto e padrões de teste que os demais tickets copiam.

**Gates:** Persistência (schema, seed); Contratos (`search_products`). Ordem de execução: 01 de 12 (série 01→12). ADRs: 0002.

- [x] Python 3.13 via `uv` (`pyproject.toml` + lockfile commitado); `uv run pytest` passa sem rede e sem chave de API
- [x] Dependências de runtime (`litellm`, `chainlit`, `tzdata`) já adicionadas e resolvidas no lockfile
- [x] Seed idempotente e atômico (uma transação) recria categorias, Produtos, promoções, Clientes, Pedidos e Itens do pedido a partir dos CSVs em `data/`; cria a tabela de Reclamações com `CREATE TABLE IF NOT EXISTS`; roda só na inicialização do serviço, nunca em tempo de import; caminho do banco via `DB_PATH`
- [x] Normalização na carga: coluna de busca derivada (nome + descrição + nome da categoria) em minúsculas e sem acentos; `specs` validado como JSON; datas em ISO 8601; `is_active` booleano; telefone só com dígitos; e-mail em minúsculas e sem espaços
- [x] Preços em centavos inteiros; nenhum `float` em valor monetário
- [x] `search_products(query, category?, limit)` retorna total + lista (id, nome, categoria, Preço de tabela); `limit` padrão 5, acima de 10 é limitado a 10 sem erro
- [x] Busca por tokens (AND): cada token normalizado (minúsculas, sem acento, plural simples `oes→ao` e `s` final) casa com a coluna derivada; relevância = acertos no nome ×2 + na categoria + na descrição
- [x] Produtos descontinuados nunca aparecem na busca
- [x] Consultas sempre parametrizadas
- [x] Testes contra SQLite real populado pelos CSVs reais (banco temporário), pelo seam público do `StoreService`: "violao yamaha" encontra os Yamaha da categoria Violões; total maior que `limit`; IDs 113 e 136 ausentes; seed executado 2× produz o mesmo estado
