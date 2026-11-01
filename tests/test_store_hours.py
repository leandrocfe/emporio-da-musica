"""Seam — store status and Reference date clock (ticket 05)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from emporio.clock import STORE_TIMEZONE, clock_from_env, parse_agent_now
from emporio.store_hours import StoreStatus, store_status


def at(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=STORE_TIMEZONE)


def test_weekday_during_business_hours_is_open_until_closing() -> None:
    status = store_status(at(2026, 3, 23, 10))  # Monday

    assert status == StoreStatus(is_open=True, changes_at=at(2026, 3, 23, 18))


def test_weekday_before_opening_opens_today() -> None:
    status = store_status(at(2026, 3, 24, 8, 59))  # Tuesday

    assert status == StoreStatus(is_open=False, changes_at=at(2026, 3, 24, 9))


def test_opening_and_closing_boundaries() -> None:
    assert store_status(at(2026, 3, 24, 9)).is_open is True
    assert store_status(at(2026, 3, 24, 18)).is_open is False
    assert store_status(at(2026, 3, 24, 17, 59)).is_open is True


def test_friday_after_closing_opens_saturday() -> None:
    status = store_status(at(2026, 3, 27, 18, 30))

    assert status == StoreStatus(is_open=False, changes_at=at(2026, 3, 28, 9))


def test_saturday_is_open_until_13() -> None:
    assert store_status(at(2026, 3, 28, 12, 59)) == StoreStatus(True, at(2026, 3, 28, 13))
    assert store_status(at(2026, 3, 28, 13)).is_open is False


def test_saturday_after_13_opens_monday() -> None:
    status = store_status(at(2026, 3, 28, 14))

    assert status == StoreStatus(is_open=False, changes_at=at(2026, 3, 30, 9))


def test_sunday_is_closed_and_opens_monday() -> None:
    status = store_status(at(2026, 3, 22, 11))

    assert status == StoreStatus(is_open=False, changes_at=at(2026, 3, 23, 9))


def test_agent_now_without_offset_is_store_time() -> None:
    assert parse_agent_now("2026-03-23T10:00:00") == at(2026, 3, 23, 10)


def test_agent_now_with_offset_is_converted_to_store_time() -> None:
    parsed = parse_agent_now("2026-03-23T14:00:00+00:00")  # UTC

    assert parsed == at(2026, 3, 23, 10)
    assert parsed.tzinfo == ZoneInfo("America/Campo_Grande")


def test_invalid_agent_now_fails_clearly() -> None:
    with pytest.raises(ValueError, match="AGENT_NOW"):
        parse_agent_now("amanhã cedo")


def test_clock_uses_agent_now_when_set() -> None:
    clock = clock_from_env({"AGENT_NOW": "2026-03-22T11:00:00"})

    assert clock() == at(2026, 3, 22, 11)


def test_clock_is_the_real_one_without_agent_now() -> None:
    for env in ({}, {"AGENT_NOW": ""}):
        now = clock_from_env(env)()
        assert now.tzinfo == STORE_TIMEZONE


def test_clock_from_env_rejects_invalid_value_at_build_time() -> None:
    with pytest.raises(ValueError, match="AGENT_NOW"):
        clock_from_env({"AGENT_NOW": "nope"})
