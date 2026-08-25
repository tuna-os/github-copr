"""Throughput is measured from mock's own timers, repeatably.

Adapted from koji-lag's measure-from-metadata approach
(slopfest/sandogasa). The one-off scrape in
docs/hummingbird-throughput.md found the chain at concurrency 1.0 with
--jobs 2 — a finding worth being able to re-check after any fix, which
a hand scrape is not.
"""
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "throughput", ROOT / "scripts" / "collect-cell-throughput.py"
)
throughput = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(throughput)


LOG = """\
2026-08-24T13:04:00.1Z ==> Build chain starting
2026-08-24T13:05:00.2Z INFO: Done(/builddir/SRPMS/glib2-2.87.3-1.el10.src.rpm) Config(hummingbird-ci) 2 minutes 6 seconds
2026-08-24T13:06:00.3Z INFO: Done(/builddir/SRPMS/pango-1.56.4-1.el10.src.rpm) Config(hummingbird-ci) 58 seconds
2026-08-24T13:07:00.4Z ERROR: Exception(/builddir/SRPMS/malcontent-0.14.0-1.el10.src.rpm) Config(hummingbird-ci) 1 minute 2 seconds
2026-08-24T13:10:00.5Z ==> ===== Summary
"""


def test_package_seconds_come_from_mocks_timers_not_log_stamps():
    """A worker's whole block carries its exit timestamp; mock's own
    `N minutes M seconds` is the only honest per-package number."""
    report = throughput.analyse_log(LOG)
    assert report["packages"]["glib2-2.87.3-1.el10"]["seconds"] == 126
    assert report["packages"]["pango-1.56.4-1.el10"]["seconds"] == 58


def test_a_failed_build_still_counts_its_time_and_is_named():
    report = throughput.analyse_log(LOG)
    assert report["failed"] == ["malcontent-0.14.0-1.el10"]
    assert report["packages"]["malcontent-0.14.0-1.el10"]["seconds"] == 62


def test_wall_clock_and_effective_concurrency():
    """Σ mock 246 s over a 360 s wall -> 0.68: the doc's key ratio."""
    report = throughput.analyse_log(LOG)
    assert report["wall_seconds"] == 360
    assert report["mock_seconds_total"] == 246
    assert report["effective_concurrency"] == 0.68


def test_a_log_with_no_wall_markers_degrades_honestly():
    report = throughput.analyse_log(
        "INFO: Done(/b/S/x-1-1.src.rpm) Config(c) 5 seconds\n")
    assert report["wall_seconds"] is None
    assert report["effective_concurrency"] is None
    assert report["packages"]["x-1-1"]["seconds"] == 5


def test_the_distribution_matches_the_docs_grain():
    report = throughput.analyse_log(LOG)
    assert set(report["distribution"]) == {
        "min", "p10", "median", "mean", "p90", "max"}
    assert report["distribution"]["min"] == 58
    assert report["distribution"]["max"] == 126
