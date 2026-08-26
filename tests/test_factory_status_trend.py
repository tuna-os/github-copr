"""Improvement is a measured thing, not a hand-diff of two snapshots.

The daily measurement used to overwrite its predecessor: hummingbird
served the same 570/262 names for five straight days while its nightly
banked nothing (#480's broken resume), and nothing said so. And on the
trend layer's very first real run, the regression check found ~160
names gone from repo/10/x86_64's served index (#519). These pin the
three questions the artifact must now answer about itself: what moved,
what regressed, and how long each unfinished target has sat still.
"""
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "factory_status", ROOT / "scripts" / "factory-status.py"
)
status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(status)


def report(measured_at, targets, history=None):
    body = {"measured_at": measured_at, "targets": targets,
            "unmeasured_targets": {}}
    if history is not None:
        body["history"] = history
    return body


def arch(built, needed):
    return {"built": list(built), "needed": list(needed),
            "catalog_entries": len(built) + len(needed), "indexes": []}


def test_the_first_measurement_has_nothing_to_compare_against():
    current = report("2026-08-25T04:00:00+00:00",
                     {"el10": {"x86_64": arch(["a"], ["b"])}})
    status.add_trend(current, None)
    assert current["trend"] is None
    assert current["history"] == []
    rendered = "\n".join(status.render_trend(current))
    assert "First measurement on record" in rendered


def test_deltas_and_newly_built_names_are_computed():
    previous = report("2026-08-20T17:00:00+00:00",
                      {"el10": {"x86_64": arch(["a"], ["b", "c"])}})
    current = report("2026-08-21T17:00:00+00:00",
                     {"el10": {"x86_64": arch(["a", "b"], ["c"])}})
    status.add_trend(current, previous)
    row = current["trend"]["rows"]["el10/x86_64"]
    assert row["built_delta"] == 1
    assert row["needed_delta"] == -1
    assert row["newly_built"] == ["b"]
    assert row["regressed"] == []


def test_a_previously_served_name_going_missing_is_regressed():
    """#519's shape: the union count can even GROW while a prefix loses
    names — only the name-level check sees it."""
    previous = report("2026-08-20T17:00:00+00:00",
                      {"el10": {"x86_64": arch(["harfbuzz", "glib2"], [])}})
    current = report("2026-08-25T17:00:00+00:00",
                     {"el10": {"x86_64": arch(["glib2", "new1", "new2"],
                                              ["harfbuzz"])}})
    status.add_trend(current, previous)
    row = current["trend"]["rows"]["el10/x86_64"]
    assert row["regressed"] == ["harfbuzz"]
    assert row["built_delta"] == 1  # grew overall, regressed anyway
    rendered = "\n".join(status.render_trend(current))
    assert "REGRESSED" in rendered
    assert "harfbuzz" in rendered


def test_days_without_movement_come_from_the_carried_history():
    """The #480 shape: flat for days must SAY it has been flat for days."""
    history = [
        {"measured_at": "2026-08-20T12:00:00+00:00",
         "counts": {"hummingbird/x86_64": {"built": 570, "needed": 103}}},
        {"measured_at": "2026-08-22T12:00:00+00:00",
         "counts": {"hummingbird/x86_64": {"built": 570, "needed": 103}}},
    ]
    previous = report("2026-08-24T12:00:00+00:00",
                      {"hummingbird": {"x86_64": arch(["p"] * 1, [])}},
                      history=history)
    previous["targets"]["hummingbird"]["x86_64"] = arch(
        [f"p{i}" for i in range(570)], [f"n{i}" for i in range(103)])
    current = report("2026-08-25T12:00:00+00:00",
                     {"hummingbird": {"x86_64": arch(
                         [f"p{i}" for i in range(570)],
                         [f"n{i}" for i in range(103)])}})
    status.add_trend(current, previous)
    stalled = current["trend"]["rows"]["hummingbird/x86_64"]["stalled"]
    assert stalled["days"] == 5
    assert stalled["at_least"] is True, (
        "the whole recorded history shows the same count, so the stall is "
        "AT LEAST that old — inventing precision would be lying politely")
    rendered = "\n".join(status.render_trend(current))
    assert "≥ 5 days" in rendered


def test_movement_resets_the_stall_clock():
    history = [
        {"measured_at": "2026-08-22T12:00:00+00:00",
         "counts": {"el10/x86_64": {"built": 50, "needed": 10}}},
        {"measured_at": "2026-08-23T12:00:00+00:00",
         "counts": {"el10/x86_64": {"built": 60, "needed": 5}}},
    ]
    previous = report("2026-08-24T12:00:00+00:00",
                      {"el10": {"x86_64": arch([f"p{i}" for i in range(60)],
                                               ["x"] * 5)}}, history=history)
    current = report("2026-08-25T12:00:00+00:00",
                     {"el10": {"x86_64": arch([f"p{i}" for i in range(60)],
                                              ["x"] * 5)}})
    status.add_trend(current, previous)
    stalled = current["trend"]["rows"]["el10/x86_64"]["stalled"]
    assert stalled["days"] == 2  # flat since 08-23's entry, not since 08-22
    assert stalled["at_least"] is False


def test_the_history_carries_forward_and_is_capped():
    history = [{"measured_at": f"2026-05-{d:02d}T00:00:00+00:00", "counts": {}}
               for d in range(1, 29)]
    previous = report("2026-08-24T00:00:00+00:00",
                      {"el10": {"x86_64": arch(["a"], [])}}, history=history)
    current = report("2026-08-25T00:00:00+00:00",
                     {"el10": {"x86_64": arch(["a"], [])}})
    status.add_trend(current, previous)
    assert len(current["history"]) == 29  # 28 carried + previous appended
    assert current["history"][-1]["measured_at"] == previous["measured_at"]
    assert current["history"][-1]["counts"]["el10/x86_64"]["built"] == 1

    oversized = [{"measured_at": f"2026-0{m}-{d:02d}T00:00:00+00:00",
                  "counts": {}}
                 for m in range(1, 7) for d in range(1, 29)]
    previous = report("2026-08-24T00:00:00+00:00",
                      {"el10": {"x86_64": arch(["a"], [])}}, history=oversized)
    current = report("2026-08-25T00:00:00+00:00",
                     {"el10": {"x86_64": arch(["a"], [])}})
    status.add_trend(current, previous)
    assert len(current["history"]) == status.HISTORY_LIMIT


def test_a_stale_baseline_is_a_loud_warning_not_a_footnote():
    """#448 sat unmerged for five days and nothing said so."""
    previous = report("2026-08-20T17:00:00+00:00",
                      {"el10": {"x86_64": arch(["a"], [])}})
    current = report("2026-08-25T17:00:00+00:00",
                     {"el10": {"x86_64": arch(["a"], [])}})
    status.add_trend(current, previous)
    assert current["trend"]["staleness_days"] == 5
    rendered = "\n".join(status.render_trend(current))
    assert "5 days old" in rendered
    assert "refresh PR is not merging" in rendered


def test_a_newly_measured_target_is_labelled_not_misread_as_growth():
    previous = report("2026-08-20T17:00:00+00:00", {})
    current = report("2026-08-21T17:00:00+00:00",
                     {"el10": {"aarch64": arch(["a", "b"], ["c"])}})
    status.add_trend(current, previous)
    row = current["trend"]["rows"]["el10/aarch64"]
    assert row["new"] is True
    rendered = "\n".join(status.render_trend(current))
    assert "newly measured" in rendered
