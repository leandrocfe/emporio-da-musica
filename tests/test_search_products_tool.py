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


def test_list_price_reaches_the_model_in_reais_as_an_exact_decimal_string(
    store: StoreService,
) -> None:
    result = search(store, {"query": "yamaha c40"})

    assert result["products"] == [
        {
            "id": 81,
            "name": "Yamaha C40 Nylon Natural",
            "category": "Violões",
            "list_price": "599.90",
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
    assert set(parameters["properties"]) == {"query", "category", "limit"}
    assert "palavras-chave" in parameters["properties"]["query"]["description"]
