# 04 — Detalhe do Produto com specs e Promoção expirada

**What to build:** o Cliente pergunta "e o Takamine GD20 que estava em promoção?" e a Lia mostra o Produto com specs em português, preço atual e Disponibilidade, avisando com clareza que a promoção não está mais vigente. Perguntando por um Produto descontinuado, a Lia diz que ele saiu do catálogo e oferece equivalente.

**Blocked by:** 02 — Lia responde no chat buscando Produtos; 03 — Preço e Disponibilidade corretos na busca

**Status:** ready-for-agent

**Executor:** builder — ferramenta de leitura com contrato conhecido.

**Gates:** Contratos (saída de `get_product`, registro no Assistente). Ordem de execução: 04 de 12.

- [ ] `get_product` aceita `product_id` ou `name`
- [ ] `name` com mais de um Produto correspondente → `{ambiguous: true, matches: [{id, name}]}` sem detalhes
- [ ] Saída: dados completos, categoria, specs (chaves em inglês; o modelo traduz), preços calculados (regra do ticket 03), Disponibilidade
- [ ] Specs dos 4 esquemas de chaves (cordas; guitarra/baixo; bateria; teclado) presentes no retorno
- [ ] Inclui Produtos descontinuados, sinalizados como tal e sem preços de venda (com categoria, para a Lia buscar equivalente)
- [ ] Em breve: Preço de tabela sinalizado, sem Preço no PIX e sem data
- [ ] Lista **todas** as Promoções expiradas associadas, para a Lia nunca prometê-las
- [ ] Ferramenta registrada no Assistente
- [ ] Testes: Takamine GD20 (ID 95) com Promoção expirada; ID 96 com 2 Promoções expiradas; descontinuado (ID 113) retornado e sinalizado sem preços; "Kala Barítono" ambíguo (IDs 128 e 130); Produto inexistente → `{found: false}`
