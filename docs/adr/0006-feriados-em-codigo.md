---
status: Aceito
date: 2026-11-01
---

# 0006 - Feriados calculados em código

## Contexto

O Manual de políticas (seção 2) diz "Domingo e Feriados: Fechado", mas `store_hours.py` ignorava feriados. Em domingo 01/11/2026 a Lia disse a um Cliente que a loja abriria na segunda 02/11 (Finados). O bloco dinâmico manda usar o dado calculado, então o dado específico (errado) venceu a regra genérica do Manual.

## Decisão

- Novo módulo `src/emporio/holidays.py` com `holiday_name(day) -> str | None`. Dia feriado conta como dia sem horário, tanto para "aberta agora" quanto para a próxima abertura. `StoreStatus` não muda.
- Abrangência: feriados nacionais, o estadual de Mato Grosso do Sul (11/10), os municipais de Campo Grande (13/06 Dia de Santo Antônio, padroeiro, e 26/08 Aniversário de Campo Grande, confirmados pelo mantenedor em 2026-11-01) e a Sexta-feira Santa. Carnaval e Corpus Christi ficam de fora (ponto facultativo). Novo feriado municipal é uma entrada na tabela `FIXED_HOLIDAYS`.
- Datas fixas numa tabela `{(mês, dia): nome}`; Sexta-feira Santa é a Páscoa menos 2 dias, com a Páscoa pelo algoritmo de Meeus/Butcher (calendário gregoriano).
- O prompt estático (cacheável, sem depender de `now`) traz a lista "Feriados em que a loja fecha", gerada da tabela `FIXED_HOLIDAYS` (dd/mm e nome, em ordem de data) mais a Sexta-feira Santa como data móvel. Assim a Lia sabe que a loja fecha em qualquer feriado da lista, mesmo numa data distante.
- O bloco dinâmico, com datas concretas, diz "FECHADA agora (feriado: <nome>)" quando hoje é feriado e lista os feriados de amanhã até hoje + 7; sem a linha, não há feriado nessa janela. Uma regra nova no prompt manda a Lia tratar os feriados da lista estática como loja fechada e, para um feriado que o Cliente cite e que não esteja na lista, não confirmar nem negar, informar o horário normal e sugerir confirmar pelo telefone da loja. `PROMPT_VERSION` sobe para `"3"`.
- Por que não JSON/CSV: as datas móveis exigiriam manutenção anual do arquivo. Por que não a lib `holidays`: traria uma dependência para cerca de 30 linhas de código testável.

## Consequências

- Sem dependência nova e sem manutenção anual para os feriados modelados.
- Feriado decretado fora da tabela (ex.: ponto facultativo ou feriado extraordinário) não é conhecido pelo código; a regra do prompt evita que a Lia o confirme ou negue e a encaminha ao telefone da loja.
- Fixado em teste: 2026-11-01 14:03 (domingo) abre terça 03/11 09:00; 2026-11-02 (Finados) fechada; Sexta-feira Santa em 2025, 2026 e 2027; Páscoa nos anos de borda 2000 e 2285; feriados municipais 13/06 e 26/08 (2026-08-26 fechada, abre 27/08 09:00); lista estática do prompt com os feriados da tabela em ordem de data e a Sexta-feira Santa, sem depender de `now`.
