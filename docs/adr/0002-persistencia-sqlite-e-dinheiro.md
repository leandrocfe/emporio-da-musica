---
status: Aceito
date: 2026-10-31
---

# 0002 — Persistência: SQLite recriado no seed, Reclamações preservadas, dinheiro em centavos

## Contexto

Os CSVs em `data/` são a fonte de verdade do catálogo, dos Clientes e dos Pedidos; a loja atualiza dados trocando os arquivos e reiniciando. As **Reclamações**, ao contrário, nascem no chat e não podem se perder. Os preços vêm como decimais (`599.9`) e o Preço no PIX gera meio centavo (599,90 × 0,95 = 569,905): `float` e `round()` dariam 569,90, `ROUND_HALF_UP` dá 569,91.

## Decisão

- Um único arquivo SQLite, caminho configurável por `DB_PATH` (padrão dentro de `data/`), montado como volume no Docker Compose.
- O seed roda **só na inicialização do serviço**, antes de aceitar conexões, nunca em tempo de import. Numa única transação: apaga e recria as seis tabelas de catálogo (categorias, Produtos, promoções, Clientes, Pedidos, Itens do pedido) a partir dos CSVs e executa `CREATE TABLE IF NOT EXISTS` para Reclamações. O ticket 01 cria o schema completo e semeia todos os CSVs; tickets seguintes só leem.
- Normalização na carga: telefone só dígitos; e-mail em minúsculas e sem espaços; `is_active` booleano; datas ISO 8601; `specs` validado como JSON; coluna de busca derivada (nome + descrição + nome da categoria) em minúsculas e sem acento.
- **Dinheiro em centavos inteiros** em todo o domínio; nenhum `float` em valor monetário. Descontos arredondados a centavos com `ROUND_HALF_UP` (conversão de reais via `Decimal`; desconto percentual em aritmética inteira equivalente). Conversão para reais só na saída das ferramentas.
- Uma conexão por operação (o Chainlit atende Sessões concorrentes); consultas sempre parametrizadas.

## Consequências

- Rollback = apagar o arquivo e reiniciar; só as Reclamações são estado durável e sobrevivem a novo seed.
- Sem migrations: mudança de schema do catálogo é aplicada pelo próprio seed. A tabela de Reclamações, se mudar, exigirá migração manual — aceitável no escopo.
- Testes usam SQLite temporário semeado pelos CSVs reais; valores esperados fixados: ID 81 → PIX R$ 569,91; ID 83 → PIX R$ 408,41.
