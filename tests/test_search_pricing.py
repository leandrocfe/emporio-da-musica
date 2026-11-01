"""Price and Disponibilidade rules through `StoreService.search_products` (Seam 1)."""

from pathlib import Path

from emporio.db import connect
from emporio.store import ProductSummary, StoreService


def product(store: StoreService, query: str, product_id: int) -> ProductSummary:
    result = store.search_products(query, limit=10)
    return next(p for p in result.products if p.id == product_id)


def test_without_promotion_pix_price_is_list_price_minus_five_percent(
    store: StoreService,
) -> None:
    c40 = product(store, "yamaha c40", 81)

    assert c40.list_price == 59990
    assert c40.pix_price == 56991  # 569.905 rounds half up
    assert c40.promo_price is None
    assert c40.discount_percent is None


def test_pix_price_rounds_half_up_to_the_cent(store: StoreService) -> None:
    memphis = product(store, "tagima memphis", 83)

    assert memphis.pix_price == 40841  # 408.405 rounds half up


def test_promotion_gives_promo_price_and_percent_and_no_pix(store: StoreService) -> None:
    ohana = product(store, "ohana ck-20", 121)

    assert ohana.list_price == 54900
    assert ohana.discount_percent == 20
    assert ohana.promo_price == 43920
    assert ohana.pix_price is None


def test_inactive_promotion_is_ignored(store: StoreService) -> None:
    giannini = product(store, "giannini gf-3d", 96)  # promotions 8 and 22 are inactive

    assert giannini.promo_price is None
    assert giannini.pix_price == 75991  # 799.90 * 0.95 = 759.905


def test_biggest_discount_wins_among_active_promotions(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executemany(
            "INSERT INTO promotions VALUES (?, 81, ?, 'Teste', ?)",
            [(901, 10, 1), (902, 25, 1), (903, 40, 0)],
        )
    c40 = product(StoreService(db_path), "yamaha c40", 81)

    assert c40.discount_percent == 25  # the inactive 40% does not count
    assert c40.promo_price == 44993  # 599.90 * 0.75 = 449.925
    assert c40.pix_price is None


def test_stock_thresholds_map_to_availability(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE products SET stock_quantity = 3 WHERE id = 81")
        conn.execute("UPDATE products SET stock_quantity = 4 WHERE id = 82")
        conn.execute("UPDATE products SET stock_quantity = 1 WHERE id = 83")
    store = StoreService(db_path)

    assert product(store, "yamaha c40", 81).availability == "last_units"
    assert product(store, "yamaha c70", 82).availability == "available"
    assert product(store, "tagima memphis", 83).availability == "last_units"


def test_zero_stock_is_out_of_stock(store: StoreService) -> None:
    assert product(store, "giannini gf-3d", 96).availability == "out_of_stock"


def test_last_units_with_promotion(store: StoreService) -> None:
    crafter = product(store, "crafter ht-100", 90)

    assert crafter.availability == "last_units"
    assert crafter.discount_percent == 18
    assert crafter.promo_price == 196718  # 2399.00 * 0.82 = 1967.18


def test_coming_soon_shows_up_in_text_search_with_list_price_only(store: StoreService) -> None:
    kala = product(store, "kala barítono", 130)

    assert kala.availability == "coming_soon"
    assert kala.list_price == 174900
    assert (kala.promo_price, kala.discount_percent, kala.pix_price) == (None, None, None)


def test_max_price_filters_by_effective_price(store: StoreService) -> None:
    result = store.search_products("ukulele", max_price=50000, limit=10)

    # Ohana CK-20 (121) lists at 549.00 but its promo price 439.20 fits the budget.
    assert 121 in {p.id for p in result.products}
    assert all(p.effective_price <= 50000 for p in result.products)
    assert result.total == len(result.products)


def test_min_price_filters_by_effective_price(store: StoreService) -> None:
    result = store.search_products("ukulele", min_price=45000, limit=10)

    # 121 lists at 549.00 but costs 439.20 with the promotion: below the minimum.
    assert 121 not in {p.id for p in result.products}
    assert all(p.effective_price >= 45000 for p in result.products)


def test_price_range_alone_is_a_valid_search(store: StoreService) -> None:
    result = store.search_products(min_price=100000, max_price=120000, limit=10)

    assert result.products
    assert all(100000 <= p.effective_price <= 120000 for p in result.products)


def test_coming_soon_is_excluded_whenever_a_price_bound_is_given(store: StoreService) -> None:
    everything = store.search_products("kala", limit=10)
    assert 130 in {p.id for p in everything.products}

    # 130 lists at 1749.00, inside both ranges below, yet it must not appear.
    capped = store.search_products("kala", max_price=200000, limit=10)
    floored = store.search_products("kala", min_price=100000, limit=10)

    assert 130 not in {p.id for p in capped.products}
    assert 130 not in {p.id for p in floored.products}
    assert capped.total < everything.total
    assert floored.total < everything.total


def test_yamaha_guitar_search_lists_cheaper_c70_despite_fewer_description_hits(
    store: StoreService,
) -> None:
    result = store.search_products("violao yamaha", limit=5)

    # Every token is in the name/category of all seven, so price decides:
    # C40 599.90, C70 849.00, FG800 ... (regression: the C70 used to be dropped).
    assert 82 in {p.id for p in result.products}
    prices = [p.effective_price for p in result.products]
    assert prices == sorted(prices)


def test_name_or_category_matches_come_before_description_only_matches(
    db_path: Path,
) -> None:
    with connect(db_path) as conn:
        # Roland Synth 3 Pro (144) mentions Yamaha only in the description.
        conn.execute("UPDATE products SET list_price = 100 WHERE id = 144")
    result = StoreService(db_path).search_products("yamaha", limit=10)

    # Cheapest of all, yet last of the 11 matches: the band beats the price.
    assert result.total == 11
    assert 144 not in {p.id for p in result.products}


def test_ties_on_effective_price_break_by_id(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE products SET list_price = 59990 WHERE id IN (82, 83)")
        conn.execute("DELETE FROM promotions WHERE product_id IN (81, 82, 83)")
    store = StoreService(db_path)

    ids = [p.id for p in store.search_products("violao", max_price=59990, limit=10).products]

    assert [i for i in ids if i in (81, 82, 83)] == [81, 82, 83]
