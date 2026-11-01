"""Seam — holiday calendar (ticket 14)."""

from datetime import date

import pytest

from emporio.holidays import _easter, holiday_name


@pytest.mark.parametrize(
    "good_friday",
    [date(2026, 4, 3), date(2027, 3, 26), date(2025, 4, 18), date(2285, 3, 20)],
)
def test_good_friday_is_derived_from_easter(good_friday: date) -> None:
    assert holiday_name(good_friday) == "Sexta-feira Santa"


def test_day_after_good_friday_is_not_a_holiday() -> None:
    assert holiday_name(date(2026, 4, 4)) is None


def test_fixed_national_holidays() -> None:
    assert holiday_name(date(2026, 11, 2)) == "Finados"
    assert holiday_name(date(2026, 11, 20)) == "Dia Nacional de Zumbi e da Consciência Negra"
    assert holiday_name(date(2026, 12, 25)) == "Natal"


def test_state_holiday_of_mato_grosso_do_sul() -> None:
    assert holiday_name(date(2026, 10, 11)) == "Criação do Estado de Mato Grosso do Sul"


def test_campo_grande_municipal_holidays() -> None:
    assert holiday_name(date(2026, 6, 13)) == "Dia de Santo Antônio (padroeiro de Campo Grande)"
    assert holiday_name(date(2026, 8, 26)) == "Aniversário de Campo Grande"


def test_regular_day_is_not_a_holiday() -> None:
    assert holiday_name(date(2026, 3, 23)) is None


def test_carnaval_and_corpus_christi_are_not_holidays() -> None:
    assert holiday_name(date(2026, 2, 17)) is None  # Terça de Carnaval
    assert holiday_name(date(2026, 6, 4)) is None  # Corpus Christi


@pytest.mark.parametrize(
    ("year", "easter"),
    [(2000, date(2000, 4, 23)), (2285, date(2285, 3, 22)), (2026, date(2026, 4, 5))],
)
def test_easter_algorithm_edge_years(year: int, easter: date) -> None:
    assert _easter(year) == easter


def test_good_friday_2000_coincides_with_tiradentes() -> None:
    # Easter 2000-04-23 puts Good Friday on 04-21; either way the store is closed.
    assert holiday_name(date(2000, 4, 21)) == "Tiradentes"
