"""NOAA ISD global-hourly station ingestion (Sprint 9 Stage B).

Parses NCEI's global-hourly CSV format (one file = one station-year) into
hourly 2 m air temperatures and the pre-registered daily-Tmax statistic
(docs/science/sprint9_heat_validation.md §2: max of QC-passing TMP over
06-13 UTC, requiring ≥ MIN_OBS_PER_DAY valid observations in that range).

License note (WMO Resolution 40, verified verbatim in the Stage A probe):
non-US ISD data "cannot be redistributed to other users or customers". Raw
files live ONLY in the gitignored cache; everything the repo commits is a
derived statistic with provenance. This module reads from the cache; it never
downloads and never writes outside it.

TMP field format (ISD format document): "±DDDD,Q" — scaled tenths of degC,
+9999 = missing, Q = quality code. Passing codes follow the pre-registration:
{0, 1, 4, 5, 9} (passed / passed-suspect-history / passed gross limits), plus
a physical-range gate of −40..+55 degC.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

TMP_MISSING = "+9999"
TMP_PASSING_QC = {"0", "1", "4", "5", "9"}
TMP_RANGE_C = (-40.0, 55.0)
TMAX_HOURS_UTC = range(6, 14)  # 06..13 inclusive — pre-registered
MIN_OBS_PER_DAY = 4


@dataclass(frozen=True)
class StationDailyTmax:
    """One station-day's daily maximum 2 m temperature (degC)."""

    station_id: str
    day: date
    tmax_c: float
    n_obs: int
    hour_of_max_utc: int


def parse_hourly_temps(path: Path) -> list[tuple[datetime, float]]:
    """All QC-passing (timestamp_utc, temp_c) pairs from one station-year CSV."""
    out: list[tuple[datetime, float]] = []
    with path.open(newline="", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            tmp = row.get("TMP") or ""
            if "," not in tmp:
                continue
            value_s, qc = tmp.split(",", 1)
            if value_s == TMP_MISSING or qc.strip() not in TMP_PASSING_QC:
                continue
            try:
                value_c = int(value_s) / 10.0
                when = datetime.fromisoformat(row["DATE"])
            except (ValueError, KeyError):
                continue
            if not (TMP_RANGE_C[0] <= value_c <= TMP_RANGE_C[1]):
                continue
            out.append((when, value_c))
    return out


def daily_tmax(
    path: Path,
    station_id: str,
    days: list[date],
) -> list[StationDailyTmax]:
    """Pre-registered daily Tmax for the requested days (qualifying days only).

    A day with < MIN_OBS_PER_DAY valid observations in 06-13 UTC yields no
    record — exclusions are visible to the caller as missing days, which the
    validation step counts and reports.
    """
    temps = parse_hourly_temps(path)
    wanted = set(days)
    by_day: dict[date, list[tuple[int, float]]] = {}
    for when, value_c in temps:
        if when.date() in wanted and when.hour in TMAX_HOURS_UTC:
            by_day.setdefault(when.date(), []).append((when.hour, value_c))
    out: list[StationDailyTmax] = []
    for day in days:
        obs = by_day.get(day, [])
        if len(obs) < MIN_OBS_PER_DAY:
            continue
        hour, tmax = max(obs, key=lambda hv: hv[1])
        out.append(
            StationDailyTmax(
                station_id=station_id,
                day=day,
                tmax_c=tmax,
                n_obs=len(obs),
                hour_of_max_utc=hour,
            )
        )
    return out
