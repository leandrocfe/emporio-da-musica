# 07 — Registro de Reclamação com protocolo

**What to build:** o Cliente insatisfeito conta o problema, a Lia acolhe com empatia, registra a Reclamação e devolve um Protocolo legível com o prazo de retorno de até 24 horas úteis. A equipe encontra a Reclamação gravada com Protocolo, data/hora, nome, contato, descrição e Pedido (se houver).

**Blocked by:** 02 — Lia responde no chat buscando Produtos

**Status:** approved — aguardando commit

**Executor:** builder — escrita simples sobre a tabela criada no ticket 01.

**Gates:** Persistência (Reclamações preservadas); Assíncrono/integrações (idempotência); Autorização (sem eco de dados de Pedido). Ordem de execução: 07 de 12. ADRs: 0002, 0003.

- [x] `register_complaint(name, contact, description, order_id?)` grava com data/hora e devolve Protocolo legível + prazo de 24h úteis
- [x] Prazo devolvido como texto "até 24 horas úteis" (sem cálculo de horário)
- [x] `order_id` gravado como referência livre, sem validar existência e sem ecoar dados do Pedido
- [x] Mesma descrição na mesma Sessão devolve o mesmo Protocolo (idempotência)
- [x] Tabela de Reclamações preservada entre reinicializações (o seed do catálogo não a apaga); banco em volume Docker
- [x] Única ferramenta com escrita; demais seguem somente leitura
- [x] Ferramenta registrada no Assistente
- [x] Testes: Reclamação gravada e recuperável com Protocolo; Protocolo único em N registros; mesma Sessão + descrição → mesmo Protocolo; sobrevive a novo seed

## Comments

**Da revisão do ticket 05 (2026-11-01):** a seção 7.3 do Manual manda "registrar a reclamação e encaminhar em até 24 horas úteis". O ticket 05 incluiu uma regra genérica no prompt: nunca afirmar que registrou ou encaminhou algo sem ferramenta. Este ticket deve acrescentar a regra explícita de usar a ferramenta de Reclamação e informar o Protocolo retornado, sem inventar Protocolo.
