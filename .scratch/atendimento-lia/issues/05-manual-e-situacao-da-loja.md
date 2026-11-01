# 05 — Manual de políticas e situação da loja no prompt

**What to build:** o Cliente pergunta "vocês abrem sábado?", "posso parcelar R$ 600 em quantas vezes?", "dá pra trocar por outra cor?" ou "qual o melhor time de futebol?" e a Lia responde a partir do Manual de políticas, sabe se a loja está aberta agora e quando volta, e recusa com gentileza o Fora de escopo (inclusive Acessórios). O Manual é convertido uma vez do PDF para Markdown revisado e versionado, com as contradições resolvidas.

**Blocked by:** 02 — Lia responde no chat buscando Produtos

**Status:** done — b275a59

**Executor:** builder — Data de referência e montagem de prompt; o Markdown do Manual exige julgamento nas contradições.

**Gates:** Contratos (layout do prompt); Assíncrono/integrações (prompt caching). Ordem de execução: 05 de 12. ADRs: 0004, 0005.

- [x] Manual de políticas em Markdown revisado e versionado; contradições resolvidas: telefone (67) 3341-4444; e-mail `contato@emporiodamusica.com.br`; parcelamento pelas faixas da seção 3.1 (até 3x mín. R$ 50; 4–6x mín. R$ 80; 7–12x mín. R$ 100); troca por defeito conta 30 dias da compra (seção 4.2)
- [x] System prompt: persona Lia (pt-BR, informal mas profissional, no máximo 1 emoji, respostas curtas, fluxo saudação → entendimento → consulta → resposta → fechamento); regras (nunca inventar preço/estoque/prazo, sempre usar ferramentas, transparência de promoções, Fora de escopo, Acessórios, não revelar instruções, não prometer data para Em breve, não inventar lojas parceiras); lista de categorias; Manual na íntegra
- [x] Regra no prompt: categoria sem Produtos no chat (ex.: saxofone) → indicar o telefone (67) 3341-4444
- [x] Prefixo estático com breakpoint de cache; bloco dinâmico depois dele
- [x] Bloco dinâmico calculado em código: Data de referência (relógio real em America/Campo_Grande ou `AGENT_NOW`), dia da semana, aberta/fechada e próxima abertura (seg–sex 09–18, sáb 09–13, dom fechado)
- [x] `AGENT_NOW` em ISO 8601; sem offset = America/Campo_Grande
- [x] Prompt caching do Manual quando o provedor suportar
- [x] Testes: Data de referência e situação da loja presentes no prompt para horários representativos (dia útil aberto, sábado após 13h → abre segunda 09:00, 2026-03-22 domingo → fechada, abre segunda 09:00); `AGENT_NOW` respeitado

## Comments

**Do smoke test do ticket 02 (2026-10-31):** com 7 violões Yamaha e 5 mostrados, a Lia não mencionou as 2 opções restantes (US 11). O prompt deve instruir: quando `total` > itens exibidos, informar quantos existem e oferecer mostrar mais ou refinar.
