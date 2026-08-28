"""A loop that cannot tell "still working" from "stuck" burns runners forever.

scripts/plan-converge.py decides whether a convergence dispatches another
wave. Everything it decides on is ONE number -- how many of the build order's
packages the published index does not yet serve -- compared with the same
number from the previous wave. The rules are cheap; the ways they go wrong
are not:

  NEVER STOPS     `remaining >= previous` must end the loop. Three of the four
                  waves on 2026-08-28 were mechanical "the index moved, go
                  again"; the fourth was a wall, and a loop without this rule
                  would still be running.
  STOPS TOO SOON  a first wave has no previous count. Reading a missing count
                  as zero makes wave 1 look like a wave that made no progress
                  and ends the loop before it starts.
  FALSE DONE      `done` ends the loop, so it must never be reached from an
                  index that could not be read. An unreachable index
                  understates `served`, and the ONE verdict where that flips
                  from cautious to catastrophic is this one.
  WRONG UNIVERSE  the build order's names must be read the way the index
                  answers -- by package name, not by our source-tree layout.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "plan-converge.py"

_spec = importlib.util.spec_from_file_location("plan_converge", SCRIPT)
converge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(converge)


@pytest.mark.parametrize(
    "remaining,previous,wave,expected",
    [
        (0, 10, 2, converge.DONE),
        (0, None, 1, converge.DONE),
        (5, 10, 2, converge.CONTINUE),
        (9, 10, 2, converge.CONTINUE),
        (10, None, 1, converge.CONTINUE),
        (10, 10, 2, converge.BLOCKED),
        (11, 10, 2, converge.BLOCKED),
    ],
)
def test_the_rules(remaining, previous, wave, expected) -> None:
    assert converge.decide(remaining, previous, wave, 8)[0] == expected


def test_a_first_wave_is_never_blocked() -> None:
    """No previous count is not a zero previous count."""
    verdict, why = converge.decide(673, None, 1, 3)
    assert verdict == converge.CONTINUE
    assert "first wave" in why


def test_the_budget_ends_it_even_while_it_is_still_moving() -> None:
    verdict, why = converge.decide(5, 400, 3, 3)
    assert verdict == converge.BUDGET
    assert "budget" in why


def test_the_budget_does_not_override_done() -> None:
    """Spending the last wave to close the gap is success, not exhaustion."""
    assert converge.decide(0, 5, 3, 3)[0] == converge.DONE


def test_a_blocked_verdict_says_rebuilding_will_not_help() -> None:
    """The verdict is a handoff, so it has to say what kind of work is left."""
    _, why = converge.decide(93, 93, 2, 3)
    assert "packaging change" in why


def test_the_build_order_is_read_the_way_the_index_answers() -> None:
    """Names, not paths: the index has never heard of src/gnome-51."""
    names = converge.wanted_names(
        REPO / "build-order-hummingbird-desktops.yml"
    )
    assert names, "the hummingbird build order parsed to nothing"
    assert not any("/" in name for name in names), [
        n for n in names if "/" in n
    ][:5]
    assert "gtk4" in names and "mutter" in names
    assert len(names) == len(set(names)), "a duplicated name double-counts"


def test_a_copr_only_entry_is_still_wanted(tmp_path: pathlib.Path) -> None:
    """Some tiers carry `copr_name:` with no path; dropping them undercounts.

    An undercount reads as "closer to done than we are", and at the limit as
    `done` over a build order half of which was never considered.
    """
    order = tmp_path / "order.yml"
    order.write_text(
        yaml.safe_dump(
            {
                "tiers": [
                    {
                        "name": "t0",
                        "packages": [
                            {"path": "src/deps/meson"},
                            {"copr_name": "vala"},
                            {"name": "pango"},
                            "src/deps/harfbuzz",
                        ],
                    }
                ]
            }
        )
    )
    assert converge.wanted_names(order) == [
        "meson", "vala", "pango", "harfbuzz",
    ]


def test_an_unreadable_index_can_never_produce_done(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    order = tmp_path / "order.yml"
    order.write_text(
        yaml.safe_dump({"tiers": [{"name": "t0", "packages": [{"name": "a"}]}]})
    )
    status = converge._load_status()

    def explode(url, cache):
        raise OSError("404")

    monkeypatch.setattr(status, "index_names", explode)
    measurement = converge.measure(order, ["https://example.invalid/"], tmp_path)
    # Nothing was readable, so nothing is served and the residue is the whole
    # order -- the loop must not conclude anything is done.
    assert measurement["unreachable_indexes"]
    assert measurement["remaining"] == ["a"]


def test_a_reachable_index_marks_its_packages_served(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    order = tmp_path / "order.yml"
    order.write_text(
        yaml.safe_dump(
            {"tiers": [{"name": "t0",
                        "packages": [{"name": "a"}, {"name": "b"}]}]}
        )
    )
    status = converge._load_status()
    monkeypatch.setattr(
        status, "index_names", lambda url, cache: ({"a"}, {"baseurl": url})
    )
    measurement = converge.measure(order, ["https://example.test/"], tmp_path)
    assert measurement["served"] == 1
    assert measurement["remaining"] == ["b"]


def test_several_indexes_union(tmp_path: pathlib.Path, monkeypatch) -> None:
    """A target may publish through more than one prefix (#467).

    Reading only the first is what made every build-chain product invisible
    to every buildroot; a convergence that did the same would keep rebuilding
    packages that are already served from the other prefix.
    """
    order = tmp_path / "order.yml"
    order.write_text(
        yaml.safe_dump(
            {"tiers": [{"name": "t0",
                        "packages": [{"name": "a"}, {"name": "b"}]}]}
        )
    )
    status = converge._load_status()
    answers = {"https://one/": {"a"}, "https://two/": {"b"}}
    monkeypatch.setattr(
        status, "index_names",
        lambda url, cache: (answers[url], {"baseurl": url}),
    )
    measurement = converge.measure(
        order, ["https://one/", "https://two/"], tmp_path
    )
    assert measurement["remaining"] == []


def test_the_cli_refuses_to_measure_against_nothing(
    tmp_path: pathlib.Path,
) -> None:
    """Convergence is measured against the served index, never a run result."""
    order = tmp_path / "order.yml"
    order.write_text(yaml.safe_dump({"tiers": []}))
    with pytest.raises(SystemExit) as exit_:
        converge.main(["--build-order", str(order)])
    assert "--served-index is required" in str(exit_.value)


def test_the_report_records_what_it_measured_against(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    order = tmp_path / "order.yml"
    order.write_text(
        yaml.safe_dump({"tiers": [{"name": "t0", "packages": [{"name": "a"}]}]})
    )
    status = converge._load_status()
    monkeypatch.setattr(
        status, "index_names",
        lambda url, cache: ({"a"}, {"baseurl": url, "revision": "1786016019"}),
    )
    report = tmp_path / "r.json"
    converge.main([
        "--build-order", str(order), "--served-index", "https://x/",
        "--report-json", str(report), "--cache", str(tmp_path / "c"),
    ])
    data = json.loads(report.read_text())
    assert data["verdict"] == converge.DONE
    assert data["index_provenance"][0]["revision"] == "1786016019", (
        "a verdict with no record of which index revision produced it cannot "
        "be re-checked later"
    )
