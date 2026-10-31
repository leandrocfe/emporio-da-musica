# 07 — Registro de Reclamação com protocolo

**What to build:** o Cliente insatisfeito conta o problema, a Lia acolhe com empatia, registra a Reclamação e devolve um Protocolo legível com o prazo de retorno de até 24 horas úteis. A equipe encontra a Reclamação gravada com Protocolo, data/hora, nome, contato, descrição e Pedido (se houver).

**Blocked by:** 02 — Lia responde no chat buscando Produtos

**Status:** ready-for-agent

**Executor:** builder — escrita simples sobre a tabela criada no ticket 01.

**Gates:** Persistência (Reclamações preservadas); Assíncrono/integrações (idempotência); Autorização (sem eco de dados de Pedido). Ordem de execução: 07 de 12. ADRs: 0002, 0003.

- [ ] `register_complaint(name, contact, description, order_id?)` grava com data/hora e devolve Protocolo legível + prazo de 24h úteis
- [ ] Prazo devolvido como texto "até 24 horas úteis" (sem cálculo de horário)
- [ ] `order_id` gravado como referência livre, sem validar existência e sem ecoar dados do Pedido
- [ ] Mesma descrição na mesma Sessão devolve o mesmo Protocolo (idempotência)
- [ ] Tabela de Reclamações preservada entre reinicializações (o seed do catálogo não a apaga); banco em volume Docker
- [ ] Única ferramenta com escrita; demais seguem somente leitura
- [ ] Ferramenta registrada no Assistente
- [ ] Testes: Reclamação gravada e recuperável com Protocolo; Protocolo único em N registros; mesma Sessão + descrição → mesmo Protocolo; sobrevive a novo seed
