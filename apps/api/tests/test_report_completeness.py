"""Report-completeness guard (Stage B gate ruling).

No committed file under docs/reports/ may contain unrendered ⟪⟫ template
markers — a report that ships with a placeholder is an unfinished report
masquerading as a finished one. Negative-tested against a doctored file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from aether_api import config

MARKERS = ("⟪", "⟫")


def _unrendered_markers(text: str) -> list[str]:
    return [m for m in MARKERS if m in text]


def _report_files() -> list[Path]:
    reports = config.data_root() / "docs" / "reports"
    return sorted(p for p in reports.rglob("*.md"))


def test_reports_exist() -> None:
    assert len(_report_files()) >= 5  # the repo has many gate reports


@pytest.mark.parametrize("path", _report_files(), ids=lambda p: p.name)
def test_no_unrendered_template_markers(path: Path) -> None:
    found = _unrendered_markers(path.read_text())
    assert not found, (
        f"{path.name} contains unrendered template marker(s) {found} — "
        "a placeholder shipped as a finished report"
    )


def test_guard_catches_doctored_report(tmp_path: Path) -> None:
    """Negative test: the detector must flag a marker, not silently pass."""
    doctored = tmp_path / "doctored_report.md"
    doctored.write_text("# Report\n\nValue: ⟪TODO_FILL⟫\n")
    assert _unrendered_markers(doctored.read_text()) == ["⟪", "⟫"]


def test_guard_passes_clean_text() -> None:
    assert _unrendered_markers("# Report\n\nValue: 4.5 K\n") == []
