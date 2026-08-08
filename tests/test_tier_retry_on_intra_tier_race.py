"""A tier's failures are retried once, but only if the tier produced something.

Tiers are a topological order over BuildRequires, and the ordering is not
perfect. Measured on the regenerated manifest: 43 one-way BuildRequires edges
fall INSIDE a tier -- 27 in cosmic-10, 9 in cosmic-00, 5 in gnome-04, 2 in
niri-15. Packages within a tier build concurrently, so those packages start
before the thing they need exists.

They are real edges, read from the Fedora specs, not artifacts of the analysis:

    libepoxy   BuildRequires  mutter            both in gnome-04
    libdecor   BuildRequires  gtk3              both in gnome-04
    libsoup3   BuildRequires  glib-networking   both in gnome-04

A second pass fixes exactly this class by construction: mutter is in the local
repo by the time libepoxy is retried. It does not require knowing WHY
tier_sources mis-assigns them -- two hypotheses for that have been proposed and
disproved, and this fix is independent of the answer.

The gate matters as much as the retry. If nothing built during the tier,
nothing a retry could need has appeared, so a retry is a second identical
failure at twice the cost. Without the gate this is a blanket
"try everything twice", which would double the cost of every genuine failure
in a 1248-package build.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build-chain.sh"


def build_tier_body() -> str:
    text = SCRIPT.read_text()
    match = re.search(r"^build_tier\(\) \{.*?^\}$", text, re.S | re.M)
    assert match, "build_tier not found"
    return match.group(0)


def test_failures_are_retried_once() -> None:
    body = build_tier_body()
    assert "retry" in body.lower(), "a tier's failures are never retried"
    assert "build_package" in body.split("_tier_start_rpms")[-1], (
        "the retry path never actually rebuilds anything"
    )


def test_the_retry_is_gated_on_the_repo_growing() -> None:
    """Ungated, this doubles the cost of every genuine failure."""
    body = build_tier_body()
    assert "_tier_start_rpms" in body, "no snapshot of the repo before the tier"
    gate = [
        line
        for line in body.splitlines()
        if "_tier_start_rpms" in line and "-gt" in line
    ]
    assert gate, (
        "the retry is not gated on the repo having grown -- it will re-run "
        "every failure a second time for nothing"
    )


def test_the_snapshot_is_taken_before_the_tier_runs() -> None:
    body = build_tier_body()
    snap = body.index("_tier_start_rpms=")
    gate = body.rindex("_tier_start_rpms")
    assert snap < gate, "the before-count is taken after the tier, not before"


def test_retry_failures_are_still_reported() -> None:
    """A package that fails twice must not be silently dropped from the tally."""
    body = build_tier_body()
    tail = body.split("_tier_start_rpms")[-1]
    assert "_tier_failed+=" in tail, (
        "a package that fails its retry is not recorded as failed, so the run "
        "would report success with packages missing"
    )
