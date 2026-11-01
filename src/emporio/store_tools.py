"""Store tools exposed to the model: argument validation and output shaping.

The Store (`StoreService`) owns the business rules and works in integer
cents; this layer validates what the model sent and converts money to reais
only on the way out (ADR-0002). Money leaves as an exact decimal string with
two places ("599.90"): JSON numbers would round-trip through float, and a
string never shows up as 599.9 or 599.8999.
"""

from collections.abc import Mapping

from emporio.money import to_brl
from emporio.store import DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT, ProductSummary, StoreService
from emporio.text import tokenize
from emporio.tools import ToolArgumentError, ToolContext, ToolRegistry, ToolResult

SEARCH_PRODUCTS_DESCRIPTION = (
    "Busca Produtos (instrumentos) no catálogo da loja por palavras-chave e/ou categoria. "
    "Retorna o total encontrado e até `limit` Produtos com id, nome, categoria e "
    'Preço de tabela em reais (string decimal, ex.: "599.90"). Cada palavra da busca '
    "precisa aparecer no Produto, então envie só palavras-chave."
)

SEARCH_PRODUCTS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                'Somente palavras-chave: tipo, marca ou modelo (ex.: "violao yamaha", '
                '"guitarra stratocaster"). Não inclua artigos, preposições nem palavras '
                'como "de", "com", "para", "iniciante", "barato".'
            ),
        },
        "category": {
            "type": "string",
            "description": 'Nome da categoria, quando o Cliente pedir um tipo (ex.: "Violões").',
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_SEARCH_LIMIT,
            "default": DEFAULT_SEARCH_LIMIT,
            "description": "Quantos Produtos listar (padrão 5, máximo 10).",
        },
    },
    "additionalProperties": False,
}


def register_store_tools(registry: ToolRegistry, store: StoreService) -> None:
    """Register every Store tool (later tickets add get_product, get_order...)."""

    def search_products(args: Mapping[str, object], ctx: ToolContext) -> ToolResult:
        query = _optional_str(args, "query")
        category = _optional_str(args, "category")
        limit = _optional_int(args, "limit", default=DEFAULT_SEARCH_LIMIT)
        if not tokenize(query or ""):
            query = None
        if category is not None and not category.strip():
            category = None
        if query is None and category is None:
            raise ToolArgumentError(
                "Informe ao menos uma palavra-chave em `query` ou uma `category`."
            )
        result = store.search_products(query=query, category=category, limit=limit)
        return {
            "total": result.total,
            "products": [_product_summary(product) for product in result.products],
        }

    registry.register(
        "search_products", SEARCH_PRODUCTS_DESCRIPTION, SEARCH_PRODUCTS_SCHEMA, search_products
    )


def _product_summary(product: ProductSummary) -> ToolResult:
    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "list_price": to_brl(product.list_price),
    }


def _optional_str(args: Mapping[str, object], key: str) -> str | None:
    value = args.get(key)
    if value is None or isinstance(value, str):
        return value
    raise ToolArgumentError(f"`{key}` deve ser texto.")


def _optional_int(args: Mapping[str, object], key: str, *, default: int) -> int:
    if key not in args:
        return default
    value = args[key]
    # bool is a subclass of int in Python; `true` is not a valid limit.
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ToolArgumentError(f"`{key}` deve ser um número inteiro.")
