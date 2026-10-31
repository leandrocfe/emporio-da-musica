# 06 — Consulta de Pedido com Verificação do pedido

**What to build:** o Cliente informa número do Pedido e e-mail ou telefone e a Lia mostra status, Itens do pedido, Valor do pedido, forma de pagamento, rastreio, Entrega prevista e, se cancelado, o motivo — chamando o Cliente pelo primeiro nome — e sabe, por prazos calculados em código, se ele ainda pode se arrepender, trocar por defeito ou acionar a garantia. Quem só sabe o número do Pedido não descobre nada: Pedido inexistente e contato errado recebem a mesma resposta, e após 3 falhas na Sessão a Lia encaminha para Atendimento humano.

**Blocked by:** 02 — Lia responde no chat buscando Produtos; 05 — Manual de políticas e situação da loja

**Status:** ready-for-agent

**Executor:** architect — autorização, anti-enumeração, estado de Sessão e prazos de pós-venda. Revisão com reviewer em `fable` (ticket crítico de autorização).

**Gates:** Autorização (actor = Sessão anônima; permitido/negado testados; anti-enumeração); Contratos (saída de `get_order`). Ordem de execução: 06 de 12. ADRs: 0001, 0003, 0005.

- [ ] `get_order(order_id, email_or_phone)`: Verificação do pedido em código; contato normalizado bate com e-mail ou telefone do dono do Pedido; telefone aceito com ou sem DDD/código do país
- [ ] Pedido inexistente, contato divergente e `order_id` inválido retornam resposta genérica idêntica
- [ ] Contador de falhas por Sessão (via `ctx`), não zera em sucesso; `order_id` inválido conta como falha
- [ ] Após 3 falhas na mesma Sessão, a ferramenta recusa com mensagem única que orienta Atendimento humano, idêntica para Pedido existente e inexistente
- [ ] Saída verificada: primeiro nome, status, data, Itens do pedido, Valor do pedido gravado (nunca recalculado), forma de pagamento, rastreio, Entrega prevista, observações
- [ ] Saída verificada inclui janelas de pós-venda calculadas em código com a Data de referência: arrependimento (7 dias da Entrega prevista), troca por defeito (30 dias da data do Pedido), garantia legal (90 dias da Entrega prevista), cada uma com `until`, `within` e `borderline` (≤2 dias); `shipped` com Entrega prevista vencida → `overdue: true`
- [ ] Nenhum dado de outro Cliente na saída
- [ ] Ferramenta registrada no Assistente
- [ ] Testes: verificação por e-mail; telefone `+55 (67) 99789-0123`, `67997890123` e `997890123` aceitos para o Pedido 7; resposta idêntica para inexistente vs. contato errado; bloqueio após 3 falhas; Valor do pedido dos Pedidos 3 e 20 igual ao gravado (3450 e 1400); Pedido 7 em 2026-03-23 → arrependimento e troca por defeito vencidos, garantia legal vigente; Pedido 8 `overdue`
