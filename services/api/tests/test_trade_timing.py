"""交易日归属必须覆盖截止时刻、长假、补班、时区与未知日历。"""

from datetime import datetime

import pytest

from app.core.exceptions import ValidationError
from app.trading_calendar import nav_day


@pytest.mark.parametrize(
    "submitted,expected",
    [
        ("2026-11-06T14:59:59+08:00", "2026-11-06"),
        ("2026-11-06T15:00:00+08:00", "2026-11-09"),
        ("2026-11-06T15:00:01+08:00", "2026-11-09"),
        ("2026-11-07T10:00:00+08:00", "2026-11-09"),
        ("2026-09-30T14:59:59+08:00", "2026-09-30"),
        ("2026-09-30T15:00:00+08:00", "2026-10-08"),
        ("2026-10-10T10:00:00+08:00", "2026-10-12"),
        ("2026-02-13T15:00:00+08:00", "2026-02-24"),
        ("2025-09-30T15:00:00+08:00", "2025-10-09"),
        ("2026-11-06T06:59:59+00:00", "2026-11-06"),
        ("2026-11-06T07:00:00+00:00", "2026-11-09"),
    ],
)
def test_nav_day(submitted, expected):
    assert nav_day(datetime.fromisoformat(submitted)).isoformat() == expected


@pytest.mark.parametrize(
    "submitted", ["2027-01-01T12:00:00+08:00", "2026-11-06T12:00:00", "2026-12-31T15:00:00+08:00"]
)
def test_unknown_year_or_missing_timezone_rejected(submitted):
    with pytest.raises(ValidationError):
        nav_day(datetime.fromisoformat(submitted))
