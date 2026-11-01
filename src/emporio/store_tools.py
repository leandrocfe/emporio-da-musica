"""Store tools exposed to the model: argument validation and output shaping.

The Store (`StoreService`) owns the business rules and works in integer
cents; this layer validates what the model sent and converts money to reais
only on the way out (ADR-0002). Money leaves as an exact decimal string with
two places ("599.90"): JSON numbers would round-trip through float, and a
string never shows up as 599.9 or 599.8999.
"""

from collections.abc import Mapping

from emporio.money import to_brl, to_cents
from emporio.store import (
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    AmbiguousProduct,
    ProductDetail,
    ProductSummary,
    StoreService,
)
from emporio.text import tokenize
from emporio.tools import ToolArgumentError, ToolContext, ToolRegistry, ToolResult

SEARCH_PRODUCTS_DESCRIPTION = (
    "Busca Produtos (instrumentos) no catálogo da loja por palavras-chave, categoria e/ou "
    "faixa de preço. Retorna o total encontrado e até `limit` Produtos com id, nome, "
    "categoria, `list_price` (Preço de tabela) e `availability`; preços em reais como "
    'string decimal (ex.: "599.90"). Produto com Promoção vigente traz `promo_price` '
    "(Preço promocional) e `discount_percent` e não tem Preço no PIX; sem promoção traz "
    "`pix_price` (Preço no PIX). Produto Em breve (`coming_soon`) traz só `list_price`. "
    "`min_price`/`max_price` valem para o preço efetivo (promocional quando houver) e "
    "excluem Produtos Em breve. Cada palavra da busca precisa aparecer no Produto, então "
    "envie só palavras-chave."
)

GET_PRODUCT_DESCRIPTION = (
    "Detalhe completo de um Produto: descrição, categoria, `specs` (chaves em inglês; "
    "traduza ao Cliente), preços e `availability`. Informe `product_id` (de uma busca "
    "anterior) ou `name`. Preços em reais como string decimal; as regras são as de "
    "`search_products`. Se `name` corresponder a mais de um Produto, retorna "
    "`ambiguous: true`, `total` e `matches` (até 10, com id e nome), sem detalhes: "
    "pergunte qual o Cliente quer. Produto inexistente retorna `found: false`. "
    "`expired_promotions` lista "
    "Promoções que NÃO estão mais vigentes: avise que acabaram e nunca as ofereça. "
    "Produto descontinuado (`discontinued`) vem sem preços: diga que saiu do catálogo e "
    "use a categoria para buscar um equivalente com `search_products`. Produto Em breve "
    "(`coming_soon`) traz só `list_price`."
)

GET_PRODUCT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "product_id": {
            "type": "integer",
            "description": "ID do Produto, como retornado por `search_products`.",
        },
        "name": {
            "type": "string",
            "description": 'Nome (ou parte dele) do Produto, ex.: "Takamine GD20".',
        },
    },
    "additionalProperties": False,
}


def _search_schema(category_names: list[str]) -> dict[str, object]:
    return {
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
                "enum": category_names,
                "description": "Categoria, quando o Cliente pedir um tipo de instrumento.",
            },
            "min_price": {
                "type": "number",
                "minimum": 0,
                "description": "Preço efetivo mínimo em reais (ex.: 500 ou 499.90).",
            },
            "max_price": {
                "type": "number",
                "minimum": 0,
                "description": "Preço efetivo máximo em reais, o orçamento do Cliente.",
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
    """Register every Store tool (later tickets add get_order...)."""

    def search_products(args: Mapping[str, object], ctx: ToolContext) -> ToolResult:
        query = _optional_str(args, "query")
        category = _optional_str(args, "category")
        min_price = _optional_price(args, "min_price")
        max_price = _optional_price(args, "max_price")
        limit = _optional_int(args, "limit", default=DEFAULT_SEARCH_LIMIT)
        if min_price is not None and max_price is not None and min_price > max_price:
            raise ToolArgumentError("`min_price` não pode ser maior que `max_price`.")
        if not tokenize(query or ""):
            query = None
        if category is not None and not category.strip():
            category = None
        if query is None and category is None and min_price is None and max_price is None:
            raise ToolArgumentError(
                "Informe ao menos uma palavra-chave em `query`, uma `category` "
                "ou uma faixa de preço."
            )
        result = store.search_products(
            query=query, category=category, min_price=min_price, max_price=max_price, limit=limit
        )
        return {
            "total": result.total,
            "products": [_product_summary(product) for product in result.products],
        }

    def get_product(args: Mapping[str, object], ctx: ToolContext) -> ToolResult:
        product_id = _optional_id(args, "product_id")
        name = _optional_str(args, "name")
        if name is not None and not tokenize(name):
            name = None
        if product_id is None and name is None:
            raise ToolArgumentError("Informe `product_id` ou `name`.")
        found = store.get_product(product_id=product_id, name=name)
        if found is None:
            return {"found": False}
        if isinstance(found, AmbiguousProduct):
            return {
                "ambiguous": True,
                "total": found.total,
                "matches": [{"id": pid, "name": pname} for pid, pname in found.matches],
            }
        return _product_detail(found)

    registry.register("get_product", GET_PRODUCT_DESCRIPTION, GET_PRODUCT_SCHEMA, get_product)
    registry.register(
        "search_products",
        SEARCH_PRODUCTS_DESCRIPTION,
        _search_schema(store.category_names()),
        search_products,
    )


def _product_summary(product: ProductSummary) -> ToolResult:
    out: ToolResult = {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "list_price": to_brl(product.list_price),
    }
    if product.promo_price is not None:
        out["promo_price"] = to_brl(product.promo_price)
        out["discount_percent"] = product.discount_percent
    if product.pix_price is not None:
        out["pix_price"] = to_brl(product.pix_price)
    out["availability"] = product.availability
    return out


def _product_detail(product: ProductDetail) -> ToolResult:
    out: ToolResult = {
        "found": True,
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "description": product.description,
        "specs": product.specs,
        "availability": product.availability,
    }
    if product.list_price is not None:
        out["list_price"] = to_brl(product.list_price)
    if product.promo_price is not None:
        out["promo_price"] = to_brl(product.promo_price)
        out["discount_percent"] = product.discount_percent
    if product.pix_price is not None:
        out["pix_price"] = to_brl(product.pix_price)
    out["expired_promotions"] = [
        {"discount_percent": promo.discount_percent, "description": promo.description}
        for promo in product.expired_promotions
    ]
    return out


def _optional_id(args: Mapping[str, object], key: str) -> int | None:
    value = args.get(key)
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ToolArgumentError(f"`{key}` deve ser um número inteiro.")


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


def _optional_price(args: Mapping[str, object], key: str) -> int | None:
    """Reais sent by the model (int or float) to integer cents, without float error.

    Bounds are rounded to the cent, ROUND_HALF_UP (499.999 becomes 500.00).
    """
    if args.get(key) is None:
        return None
    value = args[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ToolArgumentError(f"`{key}` deve ser um número em reais.")
    try:
        # str(599.9) == "599.9": the shortest repr is what the model meant, not 599.89999...
        return to_cents(str(value))
    except ValueError as exc:  # negative, inf or nan
        raise ToolArgumentError(f"`{key}` deve ser um valor em reais maior ou igual a 0.") from exc
