"""Opening hours of the store and its situation at a given moment.

Mon-Fri 09:00-18:00, Sat 09:00-13:00, Sun and holidays closed (Manual, section
2). A holiday counts as a day without hours (see `emporio.holidays`).
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from emporio.holidays import holiday_name

# weekday() -> (opens, closes); Monday is 0. Missing day = closed.
HOURS: dict[int, tuple[time, time]] = {
    **{day: (time(9), time(18)) for day in range(5)},
    5: (time(9), time(13)),
}


@dataclass(frozen=True, slots=True)
class StoreStatus:
    is_open: bool
    changes_at: datetime  # closing time when open, next opening when closed


def store_status(now: datetime) -> StoreStatus:
    today = _hours_on(now)
    if today is not None:
        opens, closes = today
        if opens <= now.time() < closes:
            return StoreStatus(True, _at(now, closes))
    return StoreStatus(False, _next_opening(now))


def _next_opening(now: datetime) -> datetime:
    # Long enough for any run of closed days (e.g. Sat holiday, Sun, Mon holiday).
    for offset in range(15):
        day = now + timedelta(days=offset)
        hours = _hours_on(day)
        if hours is None:
            continue
        opening = _at(day, hours[0])
        if opening > now:
            return opening
    raise AssertionError("unreachable: the store opens at least once in two weeks")


def _hours_on(day: datetime) -> tuple[time, time] | None:
    if holiday_name(day.date()) is not None:
        return None
    return HOURS.get(day.weekday())


def _at(day: datetime, clock_time: time) -> datetime:
    return day.replace(hour=clock_time.hour, minute=clock_time.minute, second=0, microsecond=0)
