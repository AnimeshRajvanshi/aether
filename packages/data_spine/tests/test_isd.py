"""Tests for ISD global-hourly parsing (offline, synthetic CSV)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from aether_data_spine.isd import daily_tmax, parse_hourly_temps

HEADER = '"STATION","DATE","TMP"\n'


def _row(when: str, tmp: str) -> str:
    return f'"42182099999","{when}","{tmp}"\n'


def _write(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "42182099999.csv"
    path.write_text(HEADER + "".join(rows))
    return path


class TestParseHourly:
    def test_scaling_and_qc(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            [
                _row("2022-04-08T09:00:00", "+0420,1"),  # 42.0 C, passes
                _row("2022-04-08T10:00:00", "+9999,9"),  # missing
                _row("2022-04-08T11:00:00", "+0431,3"),  # QC 3 = erroneous, dropped
                _row("2022-04-08T12:00:00", "+0610,1"),  # 61 C: out of physical range
            ],
        )
        temps = parse_hourly_temps(path)
        assert len(temps) == 1
        assert temps[0][1] == pytest.approx(42.0)

    def test_negative_temps(self, tmp_path: Path) -> None:
        path = _write(tmp_path, [_row("2022-01-01T03:00:00", "-0055,1")])
        assert parse_hourly_temps(path)[0][1] == pytest.approx(-5.5)


class TestDailyTmax:
    def test_requires_min_obs_in_hour_range(self, tmp_path: Path) -> None:
        # Only 3 obs inside 06-13 UTC -> the day must NOT qualify.
        rows = [
            _row("2022-04-08T06:00:00", "+0380,1"),
            _row("2022-04-08T09:00:00", "+0415,1"),
            _row("2022-04-08T12:00:00", "+0405,1"),
            _row("2022-04-08T15:00:00", "+0390,1"),  # outside hour range
        ]
        path = _write(tmp_path, rows)
        out = daily_tmax(path, "42182099999", [date(2022, 4, 8)])
        assert out == []

    def test_tmax_and_hour_of_max(self, tmp_path: Path) -> None:
        rows = [
            _row("2022-04-08T06:00:00", "+0380,1"),
            _row("2022-04-08T08:00:00", "+0400,1"),
            _row("2022-04-08T10:00:00", "+0420,1"),
            _row("2022-04-08T13:00:00", "+0410,1"),
        ]
        path = _write(tmp_path, rows)
        (rec,) = daily_tmax(path, "42182099999", [date(2022, 4, 8)])
        assert rec.tmax_c == pytest.approx(42.0)
        assert rec.hour_of_max_utc == 10
        assert rec.n_obs == 4

    def test_unrequested_days_ignored(self, tmp_path: Path) -> None:
        rows = [_row(f"2022-04-07T{h:02d}:00:00", "+0400,1") for h in (6, 8, 10, 12)]
        path = _write(tmp_path, rows)
        assert daily_tmax(path, "42182099999", [date(2022, 4, 8)]) == []
