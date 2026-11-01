from emporio.store import StoreService


def test_unaccented_query_finds_yamaha_guitars_in_violoes(store: StoreService) -> None:
    result = store.search_products("violao yamaha")

    assert result.products
    assert all(p.category == "Violões" for p in result.products)
    assert all(p.name.startswith("Yamaha") for p in result.products)


def test_total_counts_every_match_while_list_respects_default_limit(store: StoreService) -> None:
    result = store.search_products("violao yamaha")

    # Yamaha guitars in Violões: 81, 82, 87, 92, 98, 104, 114.
    assert result.total == 7
    assert len(result.products) == 5


def test_list_price_is_integer_cents(store: StoreService) -> None:
    result = store.search_products("yamaha c40")

    c40 = next(p for p in result.products if p.id == 81)
    assert c40.list_price == 59990
    assert type(c40.list_price) is int


def test_discontinued_products_never_appear(store: StoreService) -> None:
    shelby = store.search_products("shelby", limit=10)
    ibanez_bass = store.search_products("ibanez bass", limit=10)

    # 113 Shelby SN-7C and 136 Ibanez Bass 2X are discontinued in products.csv;
    # 137 matches "ibanez" through its (inconsistent) description.
    assert {p.id for p in shelby.products} == {89, 107, 119}
    assert {p.id for p in ibanez_bass.products} == {137}


def test_limit_above_ten_is_clamped_to_ten(store: StoreService) -> None:
    result = store.search_products("violao", limit=50)

    assert len(result.products) == 10
    assert result.total > 10


def test_query_ignores_accents_case_and_simple_plurals(store: StoreService) -> None:
    plain = store.search_products("violao yamaha", limit=10)

    for variant in ("VIOLÃO Yamaha", "violões yamaha", "violoes YAMAHAS"):
        assert store.search_products(variant, limit=10) == plain


def test_every_token_must_match(store: StoreService) -> None:
    result = store.search_products("yamaha nylon", limit=10)

    # Yamaha + nylon: C40 (81), C70 (82), NTX1 (98), CG162S (114).
    assert {p.id for p in result.products} == {81, 82, 98, 114}


def test_name_hits_outrank_description_only_hits(store: StoreService) -> None:
    result = store.search_products("yamaha", limit=10)

    # 10 Products have Yamaha in the name; Roland Synth 3 Pro (144) only in the description.
    assert result.total == 11
    assert 144 not in {p.id for p in result.products}


def test_name_matches_are_ordered_by_price_not_by_description_repeats(
    store: StoreService,
) -> None:
    result = store.search_products("yamaha")

    # All ten Yamaha-named Products share the band, so the cheapest come first:
    # C40 (R$ 599,90), FG800 (87, R$ 699,90), C70 (82, R$ 849,00), ...
    assert [p.id for p in result.products] == [81, 87, 82, 92, 114]


def test_tokens_match_whole_words_only(store: StoreService) -> None:
    result = store.search_products("kala", limit=10)

    # Kalani (118, 122, 127) is a different brand.
    assert {p.id for p in result.products} == {116, 120, 123, 124, 126, 128, 130}


def test_category_filter_ignores_accents_and_case(store: StoreService) -> None:
    result = store.search_products("yamaha", category="violoes", limit=10)

    assert {p.id for p in result.products} == {81, 82, 87, 92, 98, 104, 114}


def test_empty_query_lists_cheapest_non_discontinued_products(store: StoreService) -> None:
    result = store.search_products(limit=3)

    # 62 active + 1 coming_soon; cheapest: 119 (159.90), 118 (179.90), 116 (199.90).
    assert result.total == 63
    assert [p.id for p in result.products] == [119, 118, 116]


def test_singular_query_matches_oes_plural_in_description(store: StoreService) -> None:
    result = store.search_products("apresentação", limit=10)

    # Only the plural "apresentações" appears in these descriptions.
    assert {p.id for p in result.products} == {98, 115, 126, 144}
