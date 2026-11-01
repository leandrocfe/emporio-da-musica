# 14 — Feriados na situação da loja

**What to build:** a situação da loja calculada em código passa a respeitar feriados, como o Manual (seção 2, "Domingo e Feriados: Fechado") já promete. Em feriado a loja está fechada, e a próxima abertura pula feriados. O bloco dinâmico do prompt avisa quando hoje é feriado e lista os feriados dos próximos 7 dias, para a Lia responder "amanhã é feriado, a loja abre?" sem contradizer o Manual.

**Blocked by:** 05 — Manual de políticas e situação da loja

**Status:** done — f41e806

**Executor:** builder

**Gates:** Contratos: o texto do bloco dinâmico muda (consumidor: Lia via prompt); `PROMPT_VERSION` sobe para `"3"` porque a regra de horário muda de sentido. Sem persistência, sem UI, sem integração externa.

## Contexto (bug de 2026-11-01)

Domingo 01/11/2026, Cliente: "amanhã é feriado. A loja vai abrir?". Lia: "Sim! A loja vai abrir amanhã (segunda-feira, 02/11/2026) às 09:00." (`logs/audit.jsonl`, sem tool call). Causa: `store_hours.py` ignora feriados (PRD: "Feriados não são modelados"), e o bloco dinâmico manda a Lia usar o dado calculado e não calcular datas. O dado específico venceu a regra genérica do Manual.

## Decisões

- **Fonte:** código, sem JSON/CSV e sem dependência nova. Datas fixas numa tabela; feriados móveis derivados da Páscoa (algoritmo de Meeus/Butcher, calendário gregoriano). Um arquivo de dados exigiria manutenção anual das datas móveis; a lib `holidays` resolveria, mas traz dependência para ~30 linhas de código testável.
- **Abrangência:** nacionais (Lei 662/1949, 6.802/1980, 14.759/2023): 01/01 Confraternização Universal, Sexta-feira Santa (Páscoa − 2), 21/04 Tiradentes, 01/05 Dia do Trabalho, 07/09 Independência, 12/10 Nossa Senhora Aparecida, 02/11 Finados, 15/11 Proclamação da República, 20/11 Dia Nacional de Zumbi e da Consciência Negra, 25/12 Natal. Estadual MS: 11/10 Criação do Estado de Mato Grosso do Sul. Carnaval e Corpus Christi ficam de fora (ponto facultativo). Municipais de Campo Grande incluídos (confirmado pelo mantenedor em 2026-11-01): 13/06 Dia de Santo Antônio (padroeiro de Campo Grande) e 26/08 Aniversário de Campo Grande.
- **Módulo:** `src/emporio/holidays.py` com `holiday_name(day: date) -> str | None` (e helper interno da Páscoa). `store_hours.py` consulta esse módulo: dia feriado conta como dia sem horário. `StoreStatus` não muda.
- **Bloco dinâmico:** quando hoje é feriado, a situação diz "FECHADA agora (feriado: <nome>); abre ...". Quando há feriados nos próximos 7 dias (amanhã até hoje + 7), acrescenta uma linha "Feriados nos próximos dias (loja fechada): dd/mm/aaaa (dia-da-semana) <nome>; ...". Sem feriados no período, nenhuma linha extra.
- **Lista estática:** o prefixo estático do prompt traz "Feriados em que a loja fecha", gerada da tabela de datas fixas (dd/mm e nome, em ordem de data) mais a Sexta-feira Santa como data móvel, sem depender de `now` (cache, ADR-0004). O bloco dinâmico mantém as datas concretas dos próximos 7 dias.
- **Regra no prompt (RULES):** feriados da lista estática significam loja fechada; para data concreta e próxima abertura vale o bloco dinâmico, e sem a linha "Feriados nos próximos dias" não há feriado nos próximos 7 dias. Para um feriado da lista numa data além desses 7 dias, a Lia diz que a loja fecha nesse feriado. Se o Cliente disser que um dia é feriado e ele não estiver na lista estática, a Lia não confirma nem nega o feriado: informa o horário normal e sugere confirmar pelo telefone da loja.

## Critérios de aceite

- [x] `store_status(2026-11-01 14:03)` (domingo) → fechada, abre terça 03/11/2026 09:00
- [x] `store_status(2026-11-02 10:00)` (Finados, segunda) → fechada, abre 03/11 09:00
- [x] Sexta-feira Santa calculada: 2026-04-03, 2027-03-26, 2025-04-18
- [x] 20/11 e 11/10 são feriado; 2026-03-23 não é
- [x] Bloco dinâmico em 2026-11-01 cita "02/11/2026", "Finados" e a abertura de terça; bloco em 2026-11-02 diz que hoje é feriado
- [x] Bloco em 2026-03-23 10:00 (Data de referência das conversas de exemplo) não ganha linha de feriado
- [x] Prefixo estático lista os feriados da tabela e a Sexta-feira Santa, sem depender de `now`
- [x] 13/06 e 26/08 são feriado (26/08/2026 fechada, abre 27/08 09:00)
- [x] `PROMPT_VERSION = "3"`; PRD (linha "Horário" e item "Calendário de feriados" de fora de escopo) e CONTEXT.md atualizados; ADR-0006 curta registra a decisão
- [x] `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` verdes
