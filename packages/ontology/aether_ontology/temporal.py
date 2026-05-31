"""Temporal types for the ontology."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator


class TimeRange(BaseModel):
    """A time interval. `end` may be None for ongoing or instantaneous events.

    If `end` is provided, it must be >= `start`. An instantaneous event has
    `start == end`. An ongoing event has `end = None`.
    """

    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime | None = None

    @model_validator(mode="after")
    def _check_order(self) -> TimeRange:
        if self.end is not None and self.end < self.start:
            raise ValueError(f"end ({self.end}) < start ({self.start})")
        return self

    @property
    def is_instantaneous(self) -> bool:
        return self.end is not None and self.end == self.start

    @property
    def is_ongoing(self) -> bool:
        return self.end is None
