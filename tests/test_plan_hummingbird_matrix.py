"""Tests for the hummingbird-desktops fan-out planner.

`scripts/plan_hummingbird_matrix.py` turns one `desktop:`/`tiers:` dispatch
input into the list of jobs `build-hummingbird-desktops.yml` should run. The
selection rules are small but load-bearing: an explicit `tiers:` must collapse
to a single job regardless of desktop, `desktop: all` must fan out to every
desktop the gap report knows about (in report order, so job N always means
the same desktop), and an unknown desktop name must fail loudly rather than
silently building nothing.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "plan_hummingbird_matrix", ROOT / "scripts" / "plan_hummingbird_matrix.py"
)
assert SPEC and SPEC.loader
phm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(phm)


REPORT = {"desktops": ["gnome", "xfce", "cosmic"]}


def test_desktops_in_preserves_report_order() -> None:
    assert phm.desktops_in(REPORT) == ["gnome", "xfce", "cosmic"]


def test_explicit_tiers_collapses_to_one_job_for_the_named_desktop() -> None:
    assert phm.plan(REPORT, desktop="gnome", tiers="layer-01,layer-02") == ["gnome"]


def test_explicit_tiers_wins_even_for_desktop_all() -> None:
    """An absolute tier list names the tiers to build across whatever desktops
    need them, so it must not be split per desktop."""
    assert phm.plan(REPORT, desktop="all", tiers="layer-01") == ["all"]


def test_desktop_all_fans_out_to_every_known_desktop_in_order() -> None:
    assert phm.plan(REPORT, desktop="all", tiers="") == ["gnome", "xfce", "cosmic"]


def test_a_single_named_desktop_is_one_job() -> None:
    assert phm.plan(REPORT, desktop="xfce", tiers="") == ["xfce"]


def test_an_unknown_desktop_fails_loudly_instead_of_building_nothing() -> None:
    with pytest.raises(SystemExit):
        phm.plan(REPORT, desktop="plasma", tiers="")
