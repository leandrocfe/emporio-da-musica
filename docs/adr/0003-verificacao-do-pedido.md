---
status: Aceito
date: 2026-10-31
---

# 0003 — Verificação do pedido: anti-enumeração e contador por Sessão

## Contexto

Não há login: quem conversa é uma **Sessão** anônima do navegador. Números de Pedido são sequenciais (1–20), então qualquer diferença de resposta entre "Pedido não existe" e "contato errado" permitiria enumerar Pedidos; tentativas ilimitadas permitiriam adivinhar contatos. A decisão de liberar dados precisa viver em código, não no prompt.

## Decisão

- **Actor**: Sessão anônima. **Permitido**: número do Pedido + contato normalizado igual ao e-mail ou ao telefone do Cliente dono daquele Pedido. **Negado**: Pedido inexistente, contato divergente, `order_id` inválido ou Sessão bloqueada.
- Todos os casos negados (exceto bloqueio) devolvem **o mesmo resultado genérico**, idêntico campo a campo. O bloqueio devolve uma única mensagem que orienta **Atendimento humano**, também idêntica exista o Pedido ou não.
- Contador `failed_verifications` vive na Sessão e chega à ferramenta pelo `ToolContext` (ADR-0001). Conta por Sessão, não por Pedido; não zera após sucesso; `order_id` inválido conta como falha. A partir da 4ª tentativa após 3 falhas, a ferramenta recusa sem consultar o banco.
- Normalização do contato: contém `@` → e-mail (minúsculas, sem espaços). Caso contrário, telefone: remove não dígitos; remove `55` se sobrarem 13 dígitos; remove `0` inicial; aceita 11 dígitos (DDD + número) ou 9 dígitos (comparados com o sufixo do telefone cadastrado).
- `register_complaint` grava `order_id` como referência livre, sem validar existência e sem ecoar dados do Pedido — validar abriria outro vetor de enumeração.

## Consequências

- Recarregar a página cria nova Sessão e zera o contador; rate limit por IP fica fora de escopo e é registrado como limitação.
- Ticket crítico (autorização): revisão com reviewer em `fable`.
