# Atendimento Empório da Música

Assistente virtual que atende clientes da Empório da Música (loja de instrumentos musicais em Campo Grande/MS) por chat de suporte, respondendo sobre catálogo, pedidos e políticas da loja.

Documentação em português; código em inglês. Cada termo traz seu nome canônico em inglês (`en:`), que é o nome usado no código.

## Language

### Catálogo

**Produto** (en: `Product`):
Instrumento musical do catálogo da loja. A loja vende exclusivamente instrumentos.
_Avoid_: Item, mercadoria

**Acessório** (en: `Accessory`):
Cordas, cabos, palhetas, pedais, amplificadores, cases — algo que a loja não vende; pedido de acessório é fora de escopo.
_Avoid_: Periférico

**Preço de tabela** (en: `list_price`):
Preço cadastrado do Produto, sem nenhum desconto.
_Avoid_: Preço cheio, preço base

**Promoção vigente** (en: `active promotion`):
Promoção vinculada a um Produto e marcada como ativa no sistema; só ela pode ser oferecida ao cliente.
_Avoid_: Oferta, desconto ativo

**Promoção expirada** (en: `expired promotion`):
Promoção registrada para um Produto mas não ativa; nunca é prometida ao cliente.

**Preço promocional** (en: `promo_price`):
Preço de tabela com o desconto da Promoção vigente aplicado; sempre apresentado junto ao Preço de tabela e ao percentual.

**Preço no PIX** (en: `pix_price`):
Preço de tabela com 5% de desconto; não se aplica a Produto com Promoção vigente (promoções não são cumulativas).

**Disponibilidade** (en: `Availability`):
Situação de venda do Produto comunicada ao cliente: disponível (`available`), últimas unidades (`last_units`), esgotado (`out_of_stock`), descontinuado (`discontinued`) ou em breve (`coming_soon`).
_Avoid_: Estoque (número exato não é exposto)

**Produto descontinuado** (en: `discontinued`):
Produto que não faz mais parte do catálogo; ao ser citado, o Assistente oferece um equivalente.

**Em breve** (en: `coming_soon`):
Produto anunciado mas ainda não vendável, sem data prevista; o Assistente nunca promete data de chegada.

### Atendimento

**Cliente** (en: `Customer`):
Pessoa cadastrada que compra na loja e conversa com o Assistente.
_Avoid_: Usuário, consumidor, comprador

**Assistente** (en: `Assistant`):
Agente virtual que atende o Cliente em nome da loja, com persona e tom definidos pelo Manual de políticas.
_Avoid_: Bot, robô

**Pedido** (en: `Order`):
Compra de um ou mais Produtos feita por um Cliente, com status pendente (`pending`), confirmado (`confirmed`), enviado (`shipped`), entregue (`delivered`) ou cancelado (`cancelled`).
_Avoid_: Compra, venda, encomenda

**Valor do pedido** (en: `order total`):
Valor gravado no Pedido no momento da compra; nunca é recalculado a partir dos preços atuais do catálogo.

**Item do pedido** (en: `order_item`):
Linha de um Pedido: um Produto e a quantidade comprada.
_Avoid_: Item (sozinho), linha, produto do pedido

**Entrega prevista** (en: `estimated_delivery`):
Data prevista de chegada do Pedido; na falta da data real de entrega, é a referência para os prazos de arrependimento e de garantia legal (a troca por defeito conta da data do Pedido), sempre declarada como aproximação ao Cliente.

**Verificação do pedido** (en: `order verification`):
Confirmação de que quem pergunta é dono do Pedido — número do Pedido mais e-mail ou telefone do cadastro; sem ela, nenhum dado do Pedido é revelado.
_Avoid_: Login, autenticação

**Sessão** (en: `session`):
Uma conversa de um Cliente com o Assistente em uma aba do navegador; guarda o histórico e as tentativas falhas de Verificação do pedido, e termina ao recarregar a página.
_Avoid_: Conexão, usuário logado

**Reclamação** (en: `Complaint`):
Insatisfação registrada pelo Assistente e encaminhada à equipe, com protocolo e retorno em até 24 horas úteis.
_Avoid_: Ticket, chamado

**Protocolo** (en: `protocol`):
Código legível e único que identifica uma Reclamação para o Cliente e para a equipe.
_Avoid_: Número do ticket, ID do chamado

**Atendimento humano** (en: `human handoff`):
Encaminhamento do Cliente à equipe da loja pelos canais oficiais, quando o Assistente não deve ou não pode resolver sozinho (verificação bloqueada, prazo limítrofe, Pedido atrasado).
_Avoid_: Suporte, escalonamento, transbordo

**Manual de políticas** (en: `store policies`):
Documento interno da loja com horários, pagamentos, trocas, frete, promoções, garantia e diretrizes de atendimento; fonte de verdade para regras.
_Avoid_: FAQ, regulamento

**Fora de escopo** (en: `out of scope`):
Pergunta que não trata de instrumentos, pedidos ou políticas da loja; o Assistente recusa com gentileza e redireciona.

**Data de referência** (en: `now`):
Momento considerado "agora" pelo Assistente para horário de funcionamento e prazos; por padrão o relógio real em America/Campo_Grande, fixável para demonstrações reproduzíveis.
