"""Holidays on which the store is closed (Manual, section 2).

Scope: national holidays, the Mato Grosso do Sul state holiday (11/10) and the
Campo Grande municipal holidays (13/06, 26/08). Carnaval and Corpus Christi are
left out on purpose (ponto facultativo, not a holiday by law). Adding a holiday
is a new entry in `FIXED_HOLIDAYS`. The movable holiday (Sexta-feira Santa)
is derived from Easter, so no yearly maintenance is needed (ADR-0006).
"""

from datetime import date, timedelta

# (month, day) -> name in pt-BR (shown to the Customer).
FIXED_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (6, 13): "Dia de Santo Antônio (padroeiro de Campo Grande)",
    (8, 26): "Aniversário de Campo Grande",
    (9, 7): "Independência do Brasil",
    (10, 11): "Criação do Estado de Mato Grosso do Sul",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Dia Nacional de Zumbi e da Consciência Negra",
    (12, 25): "Natal",
}

GOOD_FRIDAY = "Sexta-feira Santa"


def fixed_holidays_sorted() -> list[tuple[int, int, str]]:
    """Fixed-date holidays as (month, day, name), ordered by date in the year."""
    return [(month, day, name) for (month, day), name in sorted(FIXED_HOLIDAYS.items())]


def holiday_name(day: date) -> str | None:
    """Name of the holiday on `day`, or None when it is a regular day."""
    name = FIXED_HOLIDAYS.get((day.month, day.day))
    if name is not None:
        return name
    if day == _easter(day.year) - timedelta(days=2):
        return GOOD_FRIDAY
    return None


def _easter(year: int) -> date:
    """Easter Sunday in the Gregorian calendar (Meeus/Jones/Butcher algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day_minus_one = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day_minus_one + 1)
