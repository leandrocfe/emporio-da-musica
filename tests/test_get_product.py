"""`get_product` through `StoreService.get_product` (Seam 1) and as the model sees it (Seam 2)."""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from emporio.app import build_assistant
from emporio.assistant import Assistant
from emporio.db import connect
from emporio.session import Session
from emporio.store import AmbiguousProduct, ProductDetail, StoreService
from emporio.store_tools import register_store_tools
from emporio.tools import ToolRegistry

from .fakes import ScriptedLLM, asks, says, tool_call

NOW = datetime(2026, 3, 23, 10, 0, tzinfo=ZoneInfo("America/Campo_Grande"))


def detail(
    store: StoreService, product_id: int | None = None, name: str | None = None
) -> ProductDetail:
    found = store.get_product(product_id=product_id, name=name)
    assert isinstance(found, ProductDetail)
    return found


def call_tool(store: StoreService, arguments: Mapping[str, object] | str) -> dict[str, object]:
    registry = ToolRegistry()
    register_store_tools(registry, store)
    llm = ScriptedLLM([asks(tool_call("call_1", "get_product", arguments)), says("ok")])
    Assistant(llm, registry, clock=lambda: NOW).reply(Session(id="s1"), "pergunta")
    result = llm.tool_results(1)["call_1"]
    assert isinstance(result, dict)
    return result


def test_takamine_gd20_lists_its_expired_promotion(store: StoreService) -> None:
    takamine = detail(store, product_id=95)

    assert takamine.name == "Takamine GD20 Dreadnought Natural"
    assert [(p.discount_percent, p.description) for p in takamine.expired_promotions] == [
        (12, "Oferta Especial")
    ]
    assert takamine.promo_price is None
    assert takamine.pix_price is not None


def test_product_with_two_expired_promotions_lists_both(store: StoreService) -> None:
    giannini = detail(store, product_id=96)

    assert [p.discount_percent for p in giannini.expired_promotions] == [18, 40]
    assert giannini.pix_price == 75991  # same rule as the search


def test_active_promotion_gives_promo_price_and_no_pix(store: StoreService) -> None:
    ohana = detail(store, product_id=121)

    assert (ohana.promo_price, ohana.discount_percent, ohana.pix_price) == (43920, 20, None)


def test_discontinued_product_is_returned_without_sale_prices(store: StoreService) -> None:
    shelby = detail(store, product_id=113)

    assert shelby.availability == "discontinued"
    assert shelby.category == "Violões"
    assert (shelby.list_price, shelby.promo_price, shelby.pix_price) == (None, None, None)


def test_coming_soon_has_list_price_only(store: StoreService) -> None:
    kala = detail(store, product_id=130)

    assert kala.availability == "coming_soon"
    assert kala.list_price is not None
    assert (kala.promo_price, kala.pix_price) == (None, None)


def test_name_matching_several_products_is_ambiguous(store: StoreService) -> None:
    found = store.get_product(name="Kala Barítono")

    assert isinstance(found, AmbiguousProduct)
    assert [pid for pid, _ in found.matches] == [128, 130]


def test_name_is_accent_and_case_insensitive_and_finds_one(store: StoreService) -> None:
    assert detail(store, name="takamine gd20").id == 95


def test_unknown_product_is_none(store: StoreService) -> None:
    assert store.get_product(product_id=99999) is None
    assert store.get_product(name="Fender Telecaster Inexistente") is None


def test_tool_output_for_expired_promotion_has_reais_strings(store: StoreService) -> None:
    result = call_tool(store, {"product_id": 95})

    assert result["found"] is True
    assert result["expired_promotions"] == [
        {"discount_percent": 12, "description": "Oferta Especial"}
    ]
    assert "promo_price" not in result
    assert isinstance(result["pix_price"], str)
    assert "stock_quantity" not in result


def test_tool_output_for_discontinued_has_no_prices(store: StoreService) -> None:
    result = call_tool(store, {"product_id": 113})

    assert result["availability"] == "discontinued"
    assert result["category"] == "Violões"
    assert not {"list_price", "promo_price", "pix_price"} & result.keys()


def test_tool_output_for_ambiguous_name_has_no_details(store: StoreService) -> None:
    assert call_tool(store, {"name": "Kala Barítono"}) == {
        "ambiguous": True,
        "total": 2,
        "matches": [
            {"id": 128, "name": "Kala KA-B Barítono Mogno"},
            {"id": 130, "name": "Kala KA-ABP-CTG Barítono Cedar"},
        ],
    }


def test_tool_output_for_unknown_product(store: StoreService) -> None:
    assert call_tool(store, {"product_id": 99999}) == {"found": False}


def test_each_specs_key_schema_reaches_the_model(store: StoreService) -> None:
    expected_keys = {
        81: ["top", "back_sides", "neck", "strings", "scale", "electronics", "color"],  # strings
        145: ["body", "neck", "strings", "color"],  # guitar / bass
        139: ["shells", "pieces", "hardware", "color"],  # drums
        142: ["keys", "type", "polyphony", "color"],  # keyboard
    }
    for product_id, keys in expected_keys.items():
        specs = call_tool(store, {"product_id": product_id})["specs"]
        assert isinstance(specs, dict)
        assert list(specs) == keys


def test_missing_or_invalid_arguments_are_tool_errors(store: StoreService) -> None:
    for arguments in ({}, {"name": "  "}, {"product_id": "95"}, {"product_id": True}, "not json"):
        error = call_tool(store, arguments)["error"]
        assert isinstance(error, dict)
        assert error["code"] == "invalid_arguments"


def test_assembled_assistant_registers_get_product(db_path: Path) -> None:
    llm = ScriptedLLM([asks(tool_call("call_1", "get_product", {"product_id": 95})), says("ok")])

    build_assistant(llm=llm, db_path=db_path).reply(Session(id="s1"), "e o GD20?")

    result = llm.tool_results(1)["call_1"]
    assert isinstance(result, dict)
    assert result["found"] is True


def insert_product(
    db_path: Path,
    product_id: int,
    name: str,
    *,
    status: str = "active",
    specs: str = "{}",
    list_price: int = 100000,
) -> None:
    """Synthetic Product in category 1 (search_text is irrelevant to get_product)."""
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO products VALUES (?, ?, 1, 'Sintético', ?, 5, ?, ?, '2026-01-01', ?)",
            (product_id, name, list_price, status, specs, name.lower()),
        )


def test_exact_name_beats_longer_names_that_contain_it(db_path: Path) -> None:
    insert_product(db_path, 901, "Zeta Prime")
    insert_product(db_path, 902, "Zeta Prime Plus")
    store = StoreService(db_path)

    assert detail(store, name="zeta prime").id == 901
    found = store.get_product(name="zeta")
    assert isinstance(found, AmbiguousProduct)
    assert [pid for pid, _ in found.matches] == [901, 902]


def test_ambiguous_matches_are_capped_but_total_is_real(db_path: Path) -> None:
    insert_product(db_path, 905, "Yamaha Sintético Onze")  # the seed has exactly 10 Yamaha
    result = call_tool(StoreService(db_path), {"name": "Yamaha"})

    matches = result["matches"]
    assert isinstance(matches, list)
    assert result["ambiguous"] is True
    assert len(matches) == 10
    assert isinstance(result["total"], int)
    assert result["total"] == 11


def test_product_id_wins_over_name(store: StoreService) -> None:
    assert detail(store, product_id=95, name="Kala Barítono").id == 95


def test_specs_that_are_not_a_json_object_fail_loudly(db_path: Path) -> None:
    insert_product(db_path, 903, "Specs Quebradas", specs="[1, 2]")

    with pytest.raises(ValueError, match="specs of product 903"):
        StoreService(db_path).get_product(product_id=903)


def test_tool_output_for_coming_soon_has_only_list_price(store: StoreService) -> None:
    result = call_tool(store, {"product_id": 130})

    assert result["availability"] == "coming_soon"
    assert isinstance(result["list_price"], str)
    assert not {"pix_price", "promo_price", "discount_percent"} & result.keys()
    assert not any("date" in key or "data" in key for key in result)


def test_active_promotion_sets_the_price_and_only_expired_ones_are_listed(
    db_path: Path,
) -> None:
    insert_product(db_path, 904, "Com Promos", list_price=100000)
    with connect(db_path) as conn:
        conn.executemany(
            "INSERT INTO promotions VALUES (?, 904, ?, ?, ?)",
            [(911, 20, "Ativa", 1), (912, 35, "Vencida", 0)],
        )
    found = detail(StoreService(db_path), product_id=904)

    assert (found.promo_price, found.discount_percent, found.pix_price) == (80000, 20, None)
    assert [(p.discount_percent, p.description) for p in found.expired_promotions] == [
        (35, "Vencida")
    ]
