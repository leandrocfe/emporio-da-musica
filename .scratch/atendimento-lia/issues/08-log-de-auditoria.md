# 08 — Log de auditoria JSONL com mascaramento

**What to build:** a equipe (e quem roda o projeto) abre o arquivo de log e vê, por conversa, cada mensagem do Cliente, cada chamada ao LLM, cada ferramenta escolhida com argumentos e resultado, a resposta final e eventuais erros — com e-mails e telefones mascarados, para o log não virar vazamento de dados pessoais.

**Blocked by:** 02 — Lia responde no chat buscando Produtos

**Status:** done — a40d54d

**Executor:** builder — implementação de `EventSink` e mascaramento sobre seam pronto.

**Gates:** Assíncrono/integrações (logging seguro, sem PII; métrica/alerta inexistente registrada como limitação). Ordem de execução: 08 de 12. ADRs: 0001, 0004.

- [x] JSON Lines, um evento por linha, com `session_id` e timestamp
- [x] Eventos: mensagem do Cliente; chamada de LLM (modelo, latência, tokens); chamada de ferramenta (nome, argumentos, duração, sucesso/erro, resumo do resultado); resposta final; erro
- [x] E-mails e telefones mascarados em todo conteúdo registrado (argumentos, resultados, mensagens), aplicado antes da escrita, inclusive dentro de JSON aninhado
- [x] System prompt registrado por hash/versão, não por inteiro
- [x] Nome do Cliente: decisão documentada (mascarado ou registrado como limitação)
- [x] Diretório de logs montado como volume no host via Docker Compose
- [x] Testes com LLM falso: eventos gravados na ordem esperada (mensagem do Cliente → LLM → ferramenta → LLM → resposta final); e-mail e telefone mascarados em argumentos e resultados
