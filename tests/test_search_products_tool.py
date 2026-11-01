"""`search_products` as the model sees it: arguments in, JSON result back (Seam 2).

Each test scripts the model to call the tool once and inspects the tool
message the Assistant sent back on the next model call.
"""

from collections.abc import Mapping
from datetime import datetime
from zoneinfo import ZoneInfo

from emporio.assistant import Assistant
from emporio.session import Session
from emporio.store import StoreService
from emporio.store_tools import register_store_tools
from emporio.tools import ToolRegistry

from .fakes import ScriptedLLM, asks, says, tool_call

NOW = datetime(2026, 3, 23, 10, 0, tzinfo=ZoneInfo("America/Campo_Grande"))


def search(store: StoreService, arguments: Mapping[str, object] | str) -> dict[str, object]:
    """What the model receives after calling search_products with `arguments`."""
    registry = ToolRegistry()
    register_store_tools(registry, store)
    llm = ScriptedLLM([asks(tool_call("call_1", "search_products", arguments)), says("ok")])

    Assistant(llm, registry, clock=lambda: NOW).reply(Session(id="s1"), "pergunta")

    result = llm.tool_results(1)["call_1"]
    assert isinstance(result, dict)
    return result


def error_code(result: dict[str, object]) -> object:
    error = result.get("error")
    return error.get("code") if isinstance(error, dict) else None


def test_model_gets_matching_products_with_the_total(store: StoreService) -> None:
    result = search(store, {"query": "violao yamaha"})

    assert result["total"] == 7
    products = result["products"]
    assert isinstance(products, list)
    assert len(products) == 5
    assert all(p["category"] == "Violões" for p in products)


def test_prices_reach_the_model_in_reais_as_an_exact_decimal_string(
    store: StoreService,
) -> None:
    result = search(store, {"query": "yamaha c40"})

    assert result["products"] == [
        {
            "id": 81,
            "name": "Yamaha C40 Nylon Natural",
            "category": "Violões",
            "list_price": "599.90",
            "pix_price": "569.91",
            "availability": "available",
        }
    ]


def test_limit_from_the_model_is_respected(store: StoreService) -> None:
    result = search(store, {"query": "violao", "limit": 2})

    products = result["products"]
    assert isinstance(products, list)
    assert len(products) == 2


def test_category_alone_is_a_valid_search(store: StoreService) -> None:
    result = search(store, {"category": "violoes", "limit": 10})

    products = result["products"]
    assert isinstance(products, list)
    assert products
    assert all(p["category"] == "Violões" for p in products)


def test_non_integer_limit_is_an_invalid_argument(store: StoreService) -> None:
    for limit in ("5", 2.5, True, None):
        assert error_code(search(store, {"query": "violao", "limit": limit})) == "invalid_arguments"


def test_non_string_query_or_category_is_an_invalid_argument(store: StoreService) -> None:
    assert error_code(search(store, {"query": 40})) == "invalid_arguments"
    assert error_code(search(store, {"category": ["Violões"]})) == "invalid_arguments"


def test_search_without_keyword_or_category_asks_the_model_for_a_keyword(
    store: StoreService,
) -> None:
    # Punctuation-only queries tokenize to nothing and would list the whole catalog.
    for arguments in ({}, {"query": "?!"}, {"query": "  ", "category": " "}):
        result = search(store, arguments)

        assert error_code(result) == "invalid_arguments"
        error = result["error"]
        assert isinstance(error, dict)
        assert "palavra-chave" in str(error["message"])


def test_unknown_argument_is_rejected(store: StoreService) -> None:
    assert error_code(search(store, {"query": "violao", "brand": "yamaha"})) == "invalid_arguments"


def test_schema_tells_the_model_to_send_only_keywords(store: StoreService) -> None:
    registry = ToolRegistry()
    register_store_tools(registry, store)

    (definition,) = registry.definitions()
    function = definition["function"]
    assert isinstance(function, dict)
    assert function["name"] == "search_products"
    parameters = function["parameters"]
    assert isinstance(parameters, dict)
    assert set(parameters["properties"]) == {"query", "category", "min_price", "max_price", "limit"}
    assert "palavras-chave" in parameters["properties"]["query"]["description"]


def products_of(result: dict[str, object]) -> list[dict[str, object]]:
    products = result["products"]
    assert isinstance(products, list)
    return products


def test_promotion_shows_promo_price_and_percent_without_pix(store: StoreService) -> None:
    result = search(store, {"query": "ohana ck-20"})

    assert products_of(result) == [
        {
            "id": 121,
            "name": "Ohana CK-20 Concert Natural",
            "category": "Ukuleles",
            "list_price": "549.00",
            "promo_price": "439.20",
            "discount_percent": 20,
            "availability": "available",
        }
    ]


def test_max_price_in_reais_filters_by_effective_price(store: StoreService) -> None:
    result = search(store, {"query": "ukulele", "max_price": 500, "limit": 10})

    assert 121 in {p["id"] for p in products_of(result)}


def test_decimal_price_bounds_are_converted_to_cents_exactly(store: StoreService) -> None:
    # 599.90 is the C40 list price: an inclusive bound must keep it (float noise must not).
    result = search(store, {"query": "yamaha c40", "min_price": 599.9, "max_price": 599.9})

    assert [p["id"] for p in products_of(result)] == [81]


def test_price_range_alone_is_a_valid_search(store: StoreService) -> None:
    result = search(store, {"min_price": 1000, "max_price": 1200, "limit": 10})

    assert "error" not in result
    assert products_of(result)


def test_invalid_price_bounds_are_invalid_arguments(store: StoreService) -> None:
    for arguments in (
        {"query": "violao", "max_price": "500"},
        {"query": "violao", "min_price": True},
        {"query": "violao", "min_price": -1},
        {"query": "violao", "max_price": -0.01},
        {"query": "violao", "min_price": 500, "max_price": 100},
        {"query": "violao", "max_price": 1e999},
    ):
        assert error_code(search(store, arguments)) == "invalid_arguments", arguments


def test_out_of_stock_and_coming_soon_are_reported_without_exact_stock(
    store: StoreService,
) -> None:
    giannini = products_of(search(store, {"query": "giannini gf-3d"}))
    kala = products_of(search(store, {"query": "kala ka-abp-ctg"}))

    assert giannini[0]["availability"] == "out_of_stock"
    assert kala[0]["availability"] == "coming_soon"
    assert "pix_price" not in kala[0] and "promo_price" not in kala[0]
    assert "stock_quantity" not in giannini[0] and "stock" not in giannini[0]


def test_discontinued_product_is_not_found(store: StoreService) -> None:
    assert products_of(search(store, {"query": "shelby sn-7c"})) == []


def test_no_product_ever_exposes_the_exact_stock(store: StoreService) -> None:
    result = search(store, {"query": "violao", "limit": 10})

    assert all("stock_quantity" not in p for p in products_of(result))


def test_schema_lists_category_names_in_enum_and_documents_price_bounds(
    store: StoreService,
) -> None:
    registry = ToolRegistry()
    register_store_tools(registry, store)

    function = registry.definitions()[0]["function"]
    assert isinstance(function, dict)
    properties = function["parameters"]["properties"]
    assert properties["category"]["enum"] == [
        "Guitarras",
        "Baixos",
        "Baterias e Percussão",
        "Teclados e Pianos",
        "Violões",
        "Instrumentos de Sopro (Madeiras)",
        "Instrumentos de Sopro (Metais)",
        "Cordas Orquestrais",
        "Ukuleles",
    ]
    assert properties["max_price"]["type"] == "number"
    assert properties["min_price"]["minimum"] == 0
