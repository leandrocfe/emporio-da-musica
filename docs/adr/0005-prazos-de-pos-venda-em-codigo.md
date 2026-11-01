---
status: Aceito
date: 2026-10-31
---

# 0005 — Prazos de pós-venda calculados em código

## Contexto

A versão inicial do PRD deixava a Lia (o LLM) calcular prazos de arrependimento, troca e garantia a partir da **Entrega prevista**. Aritmética de datas feita pelo modelo contradiz a regra "nunca inventar prazo", e o Manual de políticas não usa uma única referência: arrependimento (4.1) e garantia legal (8.1) contam do recebimento; troca por defeito (4.2) conta da **compra**. Os dados não têm data real de entrega.

## Decisão

- `get_order` devolve, quando a Verificação do pedido passa, as janelas de pós-venda já calculadas com a Data de referência (`ctx.now`):
  - **arrependimento**: 7 dias corridos a partir da Entrega prevista;
  - **troca por defeito**: 30 dias corridos a partir da data do Pedido;
  - **garantia legal**: 90 dias corridos a partir da Entrega prevista.
- Cada janela traz `until` (data limite) e `within` (dentro do prazo). As janelas contadas da Entrega prevista (arrependimento e garantia legal) trazem também `borderline`: verdadeiro quando faltam até 2 dias para o limite ou passaram até 2 dias dele, porque a Entrega prevista é aproximação da data real de recebimento e o prazo verdadeiro pode estar deslocado. A troca por defeito conta da data do Pedido, que é exata, e por isso não tem margem: `borderline` é sempre falso. Todas as janelas só são calculadas para Pedidos `delivered`; nos demais status vêm nulas. A troca por defeito conta da data do Pedido, mas não faz sentido falar dela antes do recebimento: sem isso, um Pedido ainda não enviado poderia aparecer com a troca "vencida".
- Pedido `shipped` com Entrega prevista anterior à Data de referência recebe `overdue: true`.
- O prompt instrui a Lia a declarar a Entrega prevista como aproximação e a encaminhar ao Atendimento humano quando `borderline` ou `overdue`.

## Consequências

- Exemplo fixado em teste: Pedido 7 com Data de referência 2026-03-23 → arrependimento vencido (Entrega prevista 2026-02-17), troca por defeito vencida (Pedido de 2026-02-03), garantia legal vigente; Pedido 8 → `overdue`.
- O ticket 06 passa a depender do ticket 05 (Data de referência).
- A margem vale também depois do limite: em caso de dúvida, a Lia encaminha ao Atendimento humano em vez de negar um direito do Cliente (arrependimento é direito do CDC). Custo aceito: alguns encaminhamentos a mais.
- Exemplo de margem: Entrega prevista 2026-03-10 → arrependimento até 2026-03-17; perguntas entre 2026-03-15 e 2026-03-19 são `borderline`; 2026-03-21 é vencido sem margem.
- Desvia do texto original do PRD, que foi atualizado.
