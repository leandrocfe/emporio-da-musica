# PRD — Assistente de atendimento da Empório da Música

> Glossário de domínio em `CONTEXT.md` — os termos em **negrito** abaixo seguem esse glossário. Documentação em português; código em inglês (nomes canônicos `en:` do glossário).

## Problem Statement

A equipe da Empório da Música, loja de instrumentos musicais em Campo Grande/MS, faz todo o atendimento manualmente e está sobrecarregada com perguntas repetitivas: horário de funcionamento, status de **Pedido**, preço e **Disponibilidade** de **Produtos**, regras de troca e formas de pagamento. O **Cliente** espera resposta rápida e precisa; a equipe não consegue dar vazão, e respostas improvisadas sobre preço, estoque ou prazo geram frustração e podem configurar propaganda enganosa (como alerta o **Manual de políticas**).

Do ponto de vista técnico, o problema central é estruturar um agente com LLM que decide corretamente **quando consultar dados** (catálogo, pedidos) e **quando aplicar políticas**, lida com perguntas **Fora de escopo** e tem suas escolhas técnicas documentadas e justificadas — em Python.

## Solution

Um **Assistente** chamado **Lia**, disponível em um chat web de suporte com a identidade visual da loja. O Cliente conversa em português, com tom informal mas profissional ("um amigo que entende de música"), e a Lia:

- busca e detalha Produtos consultando o catálogo em tempo real, sempre com preço calculado corretamente (**Preço de tabela**, **Preço promocional** ou **Preço no PIX**) e Disponibilidade sem expor estoque exato;
- informa status de Pedido somente após a **Verificação do pedido** (número + e-mail ou telefone do cadastro);
- responde dúvidas sobre horários, pagamento, parcelamento, trocas, devoluções, frete, garantia e promoções com base no Manual de políticas;
- registra **Reclamações** com protocolo e prazo de retorno;
- recusa com gentileza o que é Fora de escopo, incluindo **Acessórios**, que a loja não vende.

O projeto roda com um único comando via Docker, é agnóstico de provedor de LLM (Claude por padrão, trocável por configuração) e registra em arquivo de log cada decisão do agente (quais ferramentas usou, com quais argumentos e resultado), para auditoria e para as conversas de exemplo publicadas no repositório.

## User Stories

### Cliente — conversa e persona

1. Como Cliente, quero abrir o chat e ser recebido pela Lia com uma saudação acolhedora, para que eu saiba que estou falando com a Empório da Música.
2. Como Cliente, quero ver atalhos iniciais ("Procurar instrumento", "Status do pedido", "Trocas e devoluções", "Horário e endereço"), para que eu descubra rapidamente o que a Lia sabe fazer.
3. Como Cliente, quero conversar em português informal e ser compreendido mesmo escrevendo sem acento ou com erros de digitação, para que eu não precise formalizar minha pergunta.
4. Como Cliente, quero que a Lia lembre o que já falei durante a conversa, para que eu não precise repetir informações (como o número do pedido).
5. Como Cliente, quero que a Lia me chame pelo nome quando souber, para que o atendimento pareça pessoal.
6. Como Cliente, quero respostas curtas e organizadas em listas quando houver vários Produtos, para que eu leia rápido no celular.
7. Como Cliente, quero ver um indicador de que a Lia está respondendo, para que eu saiba que minha mensagem foi recebida.
8. Como Cliente, quero receber uma mensagem amigável se algo der errado no sistema, para que eu saiba que posso tentar de novo ou falar com a loja.

### Cliente — catálogo e preços

9. Como Cliente, quero buscar instrumentos por tipo, marca ou nome (ex.: "violão Yamaha"), para que eu encontre opções do meu interesse.
10. Como Cliente, quero filtrar por faixa de preço (ex.: "violões até R$ 1000"), para que eu veja só o que cabe no meu orçamento.
11. Como Cliente, quero saber quantas opções existem além das mostradas, para que eu possa pedir mais ou refinar a busca.
12. Como Cliente, quero ver o preço de cada Produto já com o desconto correto, para que eu não seja surpreendido no pagamento.
13. Como Cliente, quero ver o Preço no PIX (5% de desconto) quando o Produto não estiver em promoção, para que eu escolha a forma de pagamento mais vantajosa.
14. Como Cliente, quero ver o preço original, o percentual de desconto e o Preço promocional quando houver **Promoção vigente**, para que eu entenda o desconto com transparência.
15. Como Cliente, quero ser informado com clareza quando uma promoção que vi não está mais ativa (**Promoção expirada**), recebendo o preço atual, para que eu não crie expectativa falsa.
16. Como Cliente, quero saber se um Produto está disponível, nas últimas unidades, esgotado, descontinuado ou **Em breve**, para que eu decida se compro agora.
17. Como Cliente, quero receber sugestões de alternativas semelhantes quando o Produto estiver esgotado ou for um **Produto descontinuado**, para que eu não saia sem opção.
18. Como Cliente, quero ver especificações de um Produto (madeiras, cordas, escala, eletrônica, cor) em português, para que eu compare modelos.
19. Como Cliente iniciante, quero pedir uma recomendação ("qual violão para quem está começando?") baseada no catálogo real, para que eu escolha com segurança.
20. Como Cliente, quero saber as categorias de instrumentos que a loja trabalha, para que eu entenda o que posso procurar.
21. Como Cliente procurando um instrumento sem resultado no catálogo do chat (ex.: saxofone), quero ser orientado a consultar a loja pelo telefone, para que eu não conclua erroneamente que a loja não trabalha com aquilo.
22. Como Cliente, quero que a Lia nunca invente preço, estoque ou prazo, para que eu possa confiar na resposta.

### Cliente — pagamento e políticas

23. Como Cliente, quero saber as formas de pagamento aceitas, para que eu me planeje.
24. Como Cliente, quero saber em quantas vezes posso parcelar um valor específico, respeitando as parcelas mínimas, para que eu escolha o parcelamento.
25. Como Cliente, quero saber se posso combinar formas de pagamento, para que eu use PIX e cartão juntos quando permitido.
26. Como Cliente, quero saber o horário de funcionamento e se a loja está aberta agora, para que eu saiba quando ir ou ligar.
27. Como Cliente falando fora do expediente, quero ser avisado de quando a equipe volta, para que eu saiba quando terei atendimento humano.
28. Como Cliente, quero saber endereço, telefone/WhatsApp e e-mail da loja, para que eu entre em contato por outros canais.
29. Como Cliente arrependido de uma compra online, quero saber se posso devolver e como funciona o reembolso, para que eu exerça meu direito.
30. Como Cliente com Produto defeituoso, quero saber se ainda estou no prazo de troca ou se devo acionar a garantia, para que eu siga o caminho certo.
31. Como Cliente, quero saber se posso trocar por outra cor ou modelo, para que eu fique com o instrumento que prefiro.
32. Como Cliente, quero saber quais itens não podem ser trocados, para que eu não tenha surpresa.
33. Como Cliente, quero saber valor e prazo de frete para Campo Grande e outras cidades, para que eu estime quando recebo.
34. Como Cliente, quero saber o que a garantia cobre e não cobre, para que eu entenda meus direitos.
35. Como Cliente, quero saber como meus dados pessoais são usados, para que eu me sinta seguro.
36. Como Cliente, quero saber quando acontecem as campanhas de promoção da loja, para que eu planeje minha compra.

### Cliente — pedidos

37. Como Cliente, quero consultar o status do meu Pedido informando o número e meu e-mail ou telefone, para que eu acompanhe minha compra.
38. Como Cliente, quero ver os itens, o **Valor do pedido**, a forma de pagamento, o código de rastreio e a **Entrega prevista**, para que eu tenha a visão completa.
39. Como Cliente com Pedido cancelado, quero saber o motivo do cancelamento, para que eu entenda o que aconteceu.
40. Como Cliente com Pedido enviado, quero saber onde rastrear o código, para que eu acompanhe a entrega.
41. Como Cliente, quero saber se ainda estou no prazo de arrependimento, troca por defeito ou garantia a partir do meu Pedido, com os prazos calculados pelo sistema (não estimados pela Lia) e a Entrega prevista declarada como aproximação, para que eu saiba minhas opções.
42. Como Cliente em situação limítrofe de prazo, ou com Pedido enviado cuja Entrega prevista já passou, quero ser encaminhado à equipe em vez de receber uma negativa automática, para que meu caso seja avaliado por uma pessoa.
43. Como Cliente que errou o e-mail ou telefone, quero uma nova chance de informar o dado, para que eu consiga consultar meu Pedido.

### Cliente — reclamações

44. Como Cliente insatisfeito, quero registrar uma Reclamação pelo chat e receber um número de protocolo, para que eu tenha comprovação do registro.
45. Como Cliente, quero saber em quanto tempo terei retorno da Reclamação, para que eu saiba quando esperar contato.
46. Como Cliente, quero ser ouvido com empatia ao reclamar, para que eu me sinta respeitado.

### Cliente — fora de escopo e segurança

47. Como Cliente procurando cordas, cabos, palhetas, pedais, amplificadores ou cases, quero ser informado com gentileza que a loja trabalha só com instrumentos, para que eu procure em outro lugar.
48. Como Cliente que fez uma pergunta sem relação com a loja, quero ser redirecionado educadamente, para que eu entenda o propósito do chat.
49. Como dono de um Pedido, quero que ninguém consiga ver meus dados apenas sabendo o número do Pedido, para que minha privacidade seja preservada.
50. Como Cliente, quero que a Lia não revele dados de outros clientes, mesmo que eu insista, para que o sistema seja confiável para todos.

### Loja

51. Como gerente da loja, quero que a Lia siga o Manual de políticas como fonte de verdade, para que o atendimento automático seja coerente com o humano.
52. Como gerente da loja, quero que a Lia nunca prometa desconto não vigente nem data para Produto Em breve, para que a loja não incorra em propaganda enganosa.
53. Como gerente da loja, quero que após várias tentativas falhas de Verificação do pedido a Lia pare de tentar e encaminhe para atendimento humano, para que dados não sejam descobertos por tentativa e erro.
54. Como equipe de atendimento, quero que as Reclamações fiquem registradas com protocolo, data, contato e descrição, para que eu dê retorno no prazo.
55. Como equipe de atendimento, quero um log de cada conversa com as ferramentas usadas, para que eu audite respostas questionadas por clientes.
56. Como responsável por privacidade, quero que e-mails e telefones apareçam mascarados no log, para que o log não vire vazamento de dados pessoais.
57. Como gerente da loja, quero poder atualizar o catálogo trocando os CSVs e reiniciando o serviço, para que o Assistente use dados atualizados.

### Desenvolvedor / visitante do repositório

58. Como desenvolvedor que conhece o projeto, quero subir o projeto com um único comando Docker após informar a chave de API, para que eu teste sem configurar ambiente Python.
59. Como desenvolvedor, quero ver no log qual ferramenta o agente escolheu para cada pergunta, para que eu entenda a decisão "consultar dados × consultar políticas".
60. Como visitante do repositório, quero ler 5 conversas de exemplo cobrindo cenários variados e não triviais, para que eu conheça o agente sem precisar rodá-lo.
61. Como desenvolvedor, quero um README em português justificando framework, modelo, arquitetura de recuperação, estratégia de prompt e tratamento de dados, para que eu entenda o raciocínio.
62. Como desenvolvedor, quero ver as suposições tomadas diante de dados inconsistentes e contradições do manual, para que eu entenda como a ambiguidade foi tratada.
63. Como desenvolvedor, quero ver as limitações conhecidas e os próximos passos, para que eu saiba onde o projeto pode evoluir.
64. Como desenvolvedor, quero entender como assistentes de código foram usados no desenvolvimento, para que eu conheça o workflow do projeto.
65. Como desenvolvedor, quero trocar o provedor de LLM (ex.: Claude → Gemini) mudando só a configuração, para que o projeto não fique preso a um fornecedor.
66. Como desenvolvedor, quero fixar a Data de referência por configuração, para que conversas de exemplo e testes sejam reproduzíveis.
67. Como desenvolvedor, quero rodar a suíte de testes sem chave de API e sem rede, para que os testes sejam rápidos, baratos e determinísticos.
68. Como desenvolvedor, quero regenerar as conversas de exemplo com um comando contra o modelo real, para que os exemplos reflitam o comportamento atual.
69. Como visitante do projeto rodando, quero abrir uma página de exemplo da loja com a Lia num painel ao lado, para que eu veja o Assistente no contexto de um site real; a página é estática e seus botões levam o cursor ao campo de pergunta da Lia, já preenchido com uma pergunta de exemplo que o visitante envia se quiser.

## Implementation Decisions

### Stack e execução

- Python 3.13, gerenciado com `uv` (`pyproject.toml` + lockfile). Versões de dependências travadas no lockfile.
- Um único serviço Docker Compose sobe o chat web na porta 8000 (`docker compose up`). Configuração via `.env` a partir de `.env.example` (`cp .env.example .env`). O log de auditoria fica em `./logs`, montado do host; o banco SQLite fica num volume nomeado (`emporio-db`), que evita problemas de permissão no Linux.
- Sem banco externo: SQLite local.

### Módulos

1. **Seed de dados** (ADR-0002) — lê os CSVs de `data/`; recria, numa única transação e só na inicialização do serviço, as tabelas de catálogo (categorias, Produtos, promoções, Clientes, Pedidos, Itens do pedido), sendo os CSVs a fonte de verdade. A tabela de Reclamações é criada se não existir e preservada entre reinicializações. Banco em arquivo SQLite único, caminho por `DB_PATH`. Normalização na carga:
   - telefone armazenado só com dígitos; e-mail em minúsculas e sem espaços;
   - coluna de busca derivada (nome + descrição + nome da categoria) em minúsculas e sem acentos;
   - `specs` validado como JSON (chaves mantidas em inglês; o LLM traduz na resposta);
   - `is_active` como booleano; datas em ISO 8601;
   - valores monetários em centavos inteiros (nunca `float`).
2. **Loja (`StoreService`)** — camada de domínio determinística sobre o SQLite; expõe as quatro ferramentas abaixo. Toda regra de negócio de preço, Disponibilidade e Verificação do pedido vive aqui, nunca no prompt. Consultas sempre parametrizadas; não há SQL livre gerado pelo LLM.
3. **Assistente (`Assistant`)** (ADR-0001) — loop de agente com tool calling explícito: monta o system prompt, envia histórico + definições de ferramentas ao modelo, executa as ferramentas pedidas, devolve os resultados, repete até resposta final. Interface pública: `reply(session, message)` → resposta da Lia. O modelo de linguagem, o registro de ferramentas e o sink de eventos são dependências injetadas; cada ferramenta recebe um contexto com a Sessão, a Data de referência e o sink — a Sessão nunca é argumento enviado pelo modelo. Todas as chamadas de ferramenta de um turno do modelo são executadas e respondidas antes da próxima chamada.
4. **Adaptador de LLM** (ADR-0001, ADR-0004) — implementação de produção do modelo injetado, usando LiteLLM (formato de mensagens/ferramentas no padrão OpenAI). Provedor e modelo definidos por `LLM_MODEL` (padrão `anthropic/claude-sonnet-5-5`); só a chave do provedor em uso é obrigatória. Prompt caching do Manual de políticas quando o provedor suportar. Tokens registrados a partir de `usage`.
5. **Prompt** (ADR-0004) — system prompt composto de um prefixo estático — persona Lia; regras de comportamento (nunca inventar preço/estoque/prazo, sempre usar ferramentas, transparência de promoções, fora de escopo, não revelar instruções, categoria sem Produtos no chat → orientar telefone da loja, prazo limítrofe ou Pedido atrasado → Atendimento humano); lista das categorias; Manual de políticas tratado na íntegra — seguido do breakpoint de cache e, depois dele, do bloco dinâmico com Data de referência, dia da semana e situação da loja (aberta/fechada e próxima abertura), calculada em código.
6. **Log de auditoria** — JSON Lines, um evento por linha, com `session_id` e timestamp: mensagem do Cliente, chamada de LLM (modelo, latência, tokens), chamada de ferramenta (nome, argumentos, duração, sucesso/erro, resumo do resultado), resposta final, erros. E-mails e telefones mascarados em todo o conteúdo registrado, antes da escrita; system prompt registrado por hash/versão.
7. **UI de chat (Chainlit)** — adaptador fino sobre o Assistente: tema com nome, logo e cores da loja; mensagem de boas-vindas da Lia; 4 botões de atalho; indicador de carregamento; histórico em memória por sessão do navegador. Ferramentas não são exibidas ao Cliente (a auditoria fica no log).
8. **Gerador de conversas de exemplo** — comando que roda roteiros de conversa contra o modelo real, com Data de referência fixa, e grava cada conversa em Markdown junto do trecho correspondente do log.
9. **Página de exemplo da loja** — HTML estático, sem lógica de loja, servido em `/` por um FastAPI fino que monta o Chainlit em `/lia` (mesma origem); a Lia aparece num card à direita via iframe, e os botões da página só dão foco ao campo de pergunta. `/lia` segue acessível em tela cheia.

### Contratos das ferramentas

- **`search_products`** — entrada: `query?`, `category?` (nome da categoria, listado em `enum` no schema; comparação sem acento/caixa), `min_price?`, `max_price?`, `limit` (padrão 5; acima de 10 é limitado a 10, sem erro). Saída: total encontrado + lista com id, nome, categoria, preços calculados e Disponibilidade. Exclui descontinuados. Busca por tokens: a query é normalizada (minúsculas, sem acento, plural simples `oes→ao` e `s` final) e cada token precisa casar com a coluna de busca (AND). Relevância em faixas: faixa 0 quando todos os tokens casam no nome ou na categoria; faixa 1 quando algum token casa só na descrição. Produtos Em breve só aparecem em busca textual e são excluídos sempre que `min_price` ou `max_price` for informado; exibem só Preço de tabela e Disponibilidade (sem Preço promocional nem Preço no PIX). Ordenação: faixa de relevância, depois preço efetivo crescente, depois id. Filtros de preço usam o preço efetivo (promocional quando houver Promoção vigente).
- **`get_product`** — entrada: `product_id` ou `name`. Saída: dados completos, categoria, specs, preços calculados, Disponibilidade e **todas** as Promoções expiradas associadas (para a Lia poder responder "essa promoção não está mais vigente"). Inclui descontinuados, sinalizados e sem preços de venda (a categoria permite buscar equivalente). Em breve: Preço de tabela sinalizado, sem Preço no PIX e sem data. `name` com mais de um Produto correspondente → `{ambiguous: true, matches: [{id, name}]}`, sem detalhes, para a Lia perguntar qual. Inexistente → `{found: false}`.
- **`get_order`** (ADR-0003, ADR-0005) — entrada: `order_id`, `email_or_phone`. Verificação do pedido em código: o contato informado (normalizado) deve bater com o e-mail ou telefone do dono daquele Pedido; telefone aceito com ou sem DDD/código do país. Pedido inexistente, contato divergente e `order_id` inválido retornam a **mesma** resposta genérica (evita enumeração). O contador de falhas vive na Sessão, conta por Sessão (não por Pedido) e não zera após sucesso; após 3 falhas, a ferramenta passa a recusar com uma mensagem única que orienta Atendimento humano, exista o Pedido ou não. Saída quando verificado: primeiro nome do Cliente, status, data, Itens do pedido, Valor do pedido gravado (nunca recalculado), forma de pagamento, rastreio, Entrega prevista, observações (motivo de cancelamento) e janelas de pós-venda calculadas em código (ver Regras de domínio), mais `overdue` para Pedido enviado com Entrega prevista vencida.
- **`register_complaint`** — entrada: `name`, `contact`, `description`, `order_id?`. Grava com data/hora e devolve Protocolo legível e único e o prazo de retorno como texto ("até 24 horas úteis", sem cálculo de horário). `order_id` é gravado como referência livre, sem validar existência nem ecoar dados do Pedido (ADR-0003). Mesma descrição na mesma Sessão devolve o mesmo Protocolo (idempotência). Única ferramenta com escrita.

### Regras de domínio

- **Preço**: com Promoção vigente → Preço de tabela, percentual e Preço promocional, sem PIX. Sem promoção → Preço de tabela e Preço no PIX (5%). Cálculo em código, em centavos inteiros, com arredondamento `ROUND_HALF_UP` (ex.: Yamaha C40, ID 81: R$ 599,90 → PIX R$ 569,91). Mais de uma Promoção vigente no mesmo Produto → vale o maior desconto (ADR-0002).
- **Disponibilidade**: `discontinued` e `coming_soon` pelo status do Produto; senão estoque 0 → `out_of_stock`; 1 a 3 → `last_units`; acima → `available`. Número exato de estoque nunca é exposto.
- **Prazos de pós-venda** (ADR-0005): calculados em código pelo `get_order` com a Data de referência, seguindo o Manual — arrependimento 7 dias corridos a partir da Entrega prevista; troca por defeito 30 dias corridos a partir da data do Pedido; garantia legal 90 dias corridos a partir da Entrega prevista. Cada janela traz data limite, se está dentro do prazo e `borderline` (até 2 dias do limite, antes ou depois) nas janelas contadas da Entrega prevista; a troca por defeito, contada da data exata do Pedido, não tem margem. Janelas só para Pedidos entregues. Pedido enviado com Entrega prevista vencida → `overdue`. A Lia declara a Entrega prevista como aproximação e encaminha ao Atendimento humano casos `borderline` ou `overdue`.
- **Data de referência**: relógio real em `America/Campo_Grande`; sobrescrevível por `AGENT_NOW` em ISO 8601 (sem offset = America/Campo_Grande; usado nas conversas de exemplo com `2026-03-23T10:00:00-04:00`, segunda-feira logo após o último Pedido do conjunto de dados).
- **Horário**: aberta seg–sex 09:00–18:00 e sáb 09:00–13:00; fechada domingo. Feriados não são modelados.

### Robustez do loop

- Limite de iterações de ferramenta por mensagem (ex.: 5); ao estourar, resposta de fallback amigável.
- Timeout e até 2 retentativas com backoff na chamada ao LLM, só em timeout, 429 e 5xx (ADR-0004); falha final → mensagem amigável ao Cliente e evento de erro no log.
- Ferramenta inexistente ou argumentos inválidos → erro estruturado devolvido ao modelo (não derruba a conversa).
- Histórico em memória por Sessão, truncado às últimas N trocas para limitar tokens, sempre cortando em fronteira de mensagem do Cliente para não separar chamada e resultado de ferramenta.

### Tratamento de dados e suposições (documentadas no README)

- Manual de políticas convertido uma vez do PDF para Markdown revisado manualmente e versionado.
- Contradições do manual resolvidas assim:
  - telefone/WhatsApp: (67) 3341-4444, conforme os dados oficiais da empresa;
  - e-mail: `contato@emporiodamusica.com.br`, sem o acento que aparece por erro de digitação;
  - parcelamento: valem as faixas da seção 3.1 — até 3x com parcela mínima de R$ 50, 4x a 6x com parcela mínima de R$ 80, 7x a 12x com parcela mínima de R$ 100;
  - troca por defeito conta 30 dias da compra (seção 4.2), não do recebimento; arrependimento e garantia legal contam do recebimento (ADR-0005);
  - "mais de 300 instrumentos" e categorias de sopro e cordas orquestrais: o catálogo do chat tem 65 Produtos (2 descontinuados); sem resultado, a Lia orienta consultar a loja pelo telefone;
  - "Black Friday em todo o catálogo": só Promoção vigente no sistema é oferecida.
- Divergências observadas e preservadas: `total_brl` difere da soma dos itens nos Pedidos 3 e 20; Pedidos pagos no PIX não refletem os 5%; Produto `coming_soon` aparece em Pedido entregue; categorias de sopro e cordas orquestrais sem Produtos; e-mail duplicado entre dois Clientes (11 e 43; sem impacto, pois a verificação é por Pedido); Produtos 135–144 com descrição que contradiz nome ou specs (ex.: "Music Man Bass 1X" descrito como Fender Jazz Bass), o que afeta a busca pela descrição; dois "Kala Barítono" distintos (ID 128 ativo, ID 130 Em breve); Produtos com mais de uma Promoção expirada (93, 96, 99); Pedido 8 enviado com Entrega prevista vencida.
- Lojas parceiras para Acessórios não existem nos dados: a Lia não inventa indicações.

### Persona

- Nome Lia, "assistente da Empório da Música"; português do Brasil; informal mas profissional; no máximo um emoji por mensagem; respostas curtas; fluxo do manual (saudação → entendimento → consulta → resposta → fechamento).

### Documentação do projeto

- README em português: como rodar (Docker e local), configuração de provedor, decisões técnicas justificadas (LiteLLM e loop explícito em vez de framework/MCP; manual inteiro no contexto em vez de RAG, com o limiar em que RAG passaria a valer; ferramentas fixas em vez de agente SQL; SQLite; Chainlit), tratamento de dados e suposições, como auditar pelo log, limitações e próximos passos, uso de assistentes de código.
- 5 conversas de exemplo em Markdown:
  1. violões até R$ 1000 (busca + PIX + esgotado);
  2. Takamine GD20 com Promoção expirada;
  3. devolução de Pedido com Verificação do pedido e prazos de pós-venda calculados (Pedido 7);
  4. Acessórios + pergunta fora de escopo;
  5. Reclamação com protocolo.

## Testing Decisions

- **Bom teste** = verifica comportamento observável pelo seam público (o que a ferramenta retorna, o que o Assistente responde/chama/registra), nunca detalhes internos (queries SQL, nomes de funções privadas, formato interno do prompt). Testes rodam sem rede e sem chave de API. Framework: pytest.
- **Seam 1 — Loja (`StoreService`)**: testes contra SQLite real populado a partir dos CSVs reais (banco temporário por teste/sessão). Cobrem:
  - preço com e sem Promoção vigente, não cumulatividade com PIX e arredondamento;
  - cada Disponibilidade (Giannini GF-3D ID 96 esgotado, Shelby SN-7C ID 113 descontinuado, Kala KA-ABP-CTG Barítono ID 130 Em breve, limite de últimas unidades);
  - busca sem acento, filtro por preço efetivo, limite e total, exclusão de descontinuados;
  - `get_product` com Promoção expirada (Takamine GD20, ID 95), nome ambíguo ("Kala Barítono": IDs 128 e 130) e inexistente;
  - Verificação do pedido por e-mail e por telefone com e sem DDD; resposta idêntica para Pedido inexistente e contato errado; bloqueio após 3 falhas;
  - janelas de pós-venda do Pedido 7 e `overdue` do Pedido 8 com Data de referência 2026-03-23;
  - Valor do pedido gravado (Pedidos 3 e 20);
  - Reclamação gravada com Protocolo, sobrevivendo a novo seed.
- **Seam 2 — Assistente (`Assistant.reply`)**: modelo de linguagem falso injetado, com roteiro de respostas (incluindo pedidos de ferramenta). Cobrem:
  - ferramenta pedida é executada com os argumentos do modelo e o resultado volta ao modelo;
  - resposta final retornada; histórico mantido entre mensagens da sessão;
  - ferramenta desconhecida/argumentos inválidos viram erro devolvido ao modelo;
  - limite de iterações e fallback; falha do LLM vira mensagem amigável;
  - eventos JSONL gravados com e-mail/telefone mascarados;
  - Data de referência e situação da loja presentes no system prompt.
- **Fora dos testes automatizados**: UI Chainlit (verificação manual no navegador: boas-vindas, atalhos, carregamento, erro) e qualidade de resposta do modelo real (coberta pelo gerador de conversas de exemplo, executado manualmente).
- **Prior art**: nenhum — repositório novo; estes testes estabelecem o padrão.

## Out of Scope

- Painel administrativo (Filament ou similar) e qualquer edição de catálogo pela interface.
- UI em Laravel/Livewire (possível evolução futura, consumindo o Assistente via API).
- Servidor MCP (as ferramentas ficam isoladas em módulo próprio, prontas para virar MCP).
- RAG/embeddings e agente text-to-SQL.
- Persistência do histórico de conversa entre sessões/recargas.
- Login/conta de Cliente; criação, alteração ou cancelamento de Pedidos; pagamentos.
- Envio real de e-mail/WhatsApp para Reclamações; cálculo de frete por CEP.
- Calendário de feriados e horários especiais de campanhas.
- Streaming token a token da resposta.
- Validação formal com Gemini ou outros provedores (suportado por configuração; testado com Claude).
- Widget flutuante (Chainlit copilot) — evolução opcional se sobrar tempo; a página de exemplo usa iframe em `/lia`.
- Lógica de loja na página de exemplo (busca, catálogo navegável, carrinho, login).

## Further Notes

- Fluxo de trabalho: este PRD → tickets (`/to-tickets`) → análise do architect → execução roteada, em série 01→10, 13, 11, 12 → revisão por ticket.
- Decisões registradas em `docs/adr/`: 0001 portas do Assistente; 0002 persistência e dinheiro; 0003 Verificação do pedido; 0004 prompt, caching, truncamento e retry; 0005 prazos de pós-venda em código.
- Uma futura UI Livewire consumiria o Assistente por uma API HTTP fina (`reply(session, message)` exposto); o desacoplamento atual já permite isso sem reescrever o núcleo.
