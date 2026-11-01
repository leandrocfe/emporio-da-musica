# 03 — Preço e Disponibilidade corretos na busca

**What to build:** o Cliente que busca "violões até R$ 1000" recebe só Produtos cujo preço efetivo cabe no orçamento, cada um com o preço correto e a Disponibilidade, sem nunca ver o estoque exato. Com Promoção vigente: Preço de tabela, percentual e Preço promocional (sem PIX). Sem promoção: Preço de tabela e Preço no PIX (5%). Toda a regra vive no `StoreService`, nunca no prompt.

**Blocked by:** 01 — Scaffold do projeto e busca textual no catálogo

**Status:** ready-for-agent

**Executor:** builder — regras puras e bem especificadas sobre o schema do ticket 01.

**Gates:** Contratos (saída de `search_products`). Ordem de execução: 03 de 12. ADRs: 0002.

- [ ] Promoção vigente → Preço promocional + Preço de tabela + percentual; sem Preço no PIX (não cumulativo)
- [ ] Mais de uma Promoção vigente no mesmo Produto → vale o maior desconto
- [ ] Sem promoção → Preço no PIX = Preço de tabela − 5%; `ROUND_HALF_UP` a centavos
- [ ] Disponibilidade: `discontinued`/`coming_soon` pelo status; senão estoque 0 → `out_of_stock`, 1–3 → `last_units`, >3 → `available`; número exato nunca na saída
- [ ] `min_price`/`max_price` filtram pelo preço efetivo (promocional quando houver)
- [ ] Produtos Em breve aparecem em busca textual e são excluídos sempre que `min_price` ou `max_price` for informado
- [ ] `category` aceita o nome da categoria sem acento/caixa; o schema da ferramenta lista os nomes em `enum`
- [ ] Ordenação: relevância textual, depois preço efetivo crescente
- [ ] Testes: ID 81 → PIX R$ 569,91; ID 83 → PIX R$ 408,41; ID 121 → Preço promocional R$ 439,20 (tabela R$ 549,00, 20%) sem PIX e dentro de `max_price` 500; ID 96 (Giannini GF-3D) `out_of_stock`; ID 113 (Shelby SN-7C) fora da busca; ID 130 (Kala KA-ABP-CTG Barítono) Em breve na busca textual e ausente com `max_price`; ID 90 `last_units` com promoção

## Comments

**Do smoke test do ticket 02 (2026-10-31):** "tem violão Yamaha?" mostrou C40, F310, FG800, CG162S (R$ 1.699) e APX600, omitindo o C70 (R$ 849), mais barato. Causa: relevância conta repetições na descrição e domina o desempate por preço. Ajuste esperado: quando todos os tokens casam, a relevância não deve sobrepor o preço efetivo crescente (ex.: relevância em faixas — nome+categoria casam vs. só descrição — e preço dentro da faixa). Teste: "violao yamaha" com limit 5 inclui o C70 (ID 82).
