"""Serving an older build than upstream is a security regression, not clutter.

The desktop manifests add our rebuild repository at `priority: 5`, and dnf's
priority is ABSOLUTE rather than a tie-break: a package from a higher-priority
repository wins even when a lower-priority one offers a newer build. Upstream's
repository carries no priority. So for any name in both indexes, ours is what
gets installed -- and if ours is older, upstream's fix is shadowed.

Hummingbird's whole premise is a zero-CVE catalogue shipped as soon as it is
published, so this is the one drift direction that matters most. Measured live
on 2026-08-25: 16 shadowed, `sudo` fifteen releases behind upstream.

Nothing catches this on its own. The gap measurement drops a package from the
BUILD ORDER the moment upstream adopts it -- which is correct -- but nothing
withdraws the copy already published, so the build set shrinks while the served
index keeps the stale build forever.

The failure modes pinned here are the ones that would make the check pass while
measuring nothing:

  * a comparison that flags the wrong direction (or nothing at all);
  * counting source rpms, which describe what built a package rather than what
    an image installs;
  * a target selector that hardcodes hummingbird, which is exactly how the
    previous reactive driver died with #517;
  * an architecture guessed rather than derived, which would compare x86_64
    against aarch64 and report the entire index as shadowed.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shadowing = load("check_upstream_shadowing", "check-upstream-shadowing.py")
vercmp = load("rpm_vercmp", "rpm_vercmp.py")


def pkg(evr: str, arch: str = "x86_64") -> dict:
    return {"evr": evr, "arch": arch, "srpm": None}


def test_an_older_served_build_is_reported() -> None:
    rows = shadowing.shadowed(
        {"sudo": pkg("1.9.17-1.p2.fc43")},
        {"sudo": pkg("1.9.17-16.p2.hum1")},
        vercmp.compare_evr,
    )
    assert [r["package"] for r in rows] == ["sudo"], (
        "a package we serve older than upstream's build was not reported; "
        "at priority 5 ours is what installs, so upstream's fix is shadowed"
    )
    assert rows[0]["served_evr"] == "1.9.17-1.p2.fc43"
    assert rows[0]["upstream_evr"] == "1.9.17-16.p2.hum1"


def test_a_newer_or_equal_served_build_is_not_reported() -> None:
    """The check must not fire on the packages we are *supposed* to serve.

    Half the overlap is ours-newer, which is the normal state for a rebuild
    that is ahead of what upstream has adopted. Reporting those would make
    the check noise and it would be turned off.
    """
    assert shadowing.shadowed(
        {"gtk4": pkg("4.22.1-2.fc43"), "pango": pkg("1.57.0-1.fc43")},
        {"gtk4": pkg("4.20.0-1.hum1"), "pango": pkg("1.57.0-1.fc43")},
        vercmp.compare_evr,
    ) == []


def test_source_rpms_are_not_compared() -> None:
    """A src entry describes what BUILT a package, not what installs."""
    assert shadowing.shadowed(
        {"sudo": pkg("1.9.17-1.p2.fc43", arch="src")},
        {"sudo": pkg("1.9.17-16.p2.hum1", arch="src")},
        vercmp.compare_evr,
    ) == []


def test_only_targets_declaring_both_halves_are_checked() -> None:
    """Generic over targets, and hummingbird is one of them.

    Both assertions matter. Selecting a target that declares no upstream
    index would fail on a URL it never had; hardcoding hummingbird is what
    made the previous reactive driver disappear with the rest of the
    hummingbird-specific pipeline.
    """
    factory = {
        "targets": {
            "declared": {
                "r2_path": "declared/20260101-x86_64",
                "gap_measurement": {"target_index": "https://example.invalid/$arch/"},
            },
            "no_upstream_index": {
                "r2_path": "other/20260101-x86_64",
                "gap_measurement": {},
            },
            "no_served_prefix": {
                "gap_measurement": {"target_index": "https://example.invalid/$arch/"},
            },
        }
    }
    assert [n for n, _ in shadowing.targets_to_check(factory)] == ["declared"]

    real = __import__("yaml").safe_load(
        (ROOT / "manifests" / "package-factory.yaml").read_text())
    assert "hummingbird" in [n for n, _ in shadowing.targets_to_check(real)], (
        "hummingbird declares both r2_path and gap_measurement.target_index, "
        "so it must be selected without being named in the code"
    )


def test_the_architecture_is_derived_not_guessed() -> None:
    assert shadowing.arch_of("hummingbird/20251124-x86_64") == "x86_64"
    assert shadowing.arch_of("hummingbird/20251124-aarch64") == "aarch64"
    assert shadowing.arch_of("anything/at-all", override="ppc64le") == "ppc64le"
    with pytest.raises(ValueError):
        # Defaulting here would compare one architecture's index against
        # another's and report every package as shadowed.
        shadowing.arch_of("hummingbird/20251124")


def test_the_reactive_driver_actually_runs_the_check() -> None:
    """A check nothing invokes is the failure this repository keeps repeating.

    The mock root cache sat unused for weeks because the workflow that set
    MOCK_CACHE_DIR was deleted; the drift re-measure went inert because its
    driver was removed while the script was kept. Both were silent. So the
    wiring is pinned, not just the script.

    It belongs in `remeasure`, which runs only when upstream's revision has
    actually moved -- that is precisely when a package we serve can become
    the older build -- rather than in the hourly `detect` gate, which must
    stay cheap.
    """
    workflow = (ROOT / ".github" / "workflows" / "upstream-drift.yml")
    text = workflow.read_text(encoding="utf-8")
    assert "check-upstream-shadowing.py" in text, (
        "upstream-drift.yml does not run the shadowing check, so nothing "
        "notices when our published copy becomes older than upstream's"
    )
    body = __import__("yaml").safe_load(text)
    steps = body["jobs"]["remeasure"]["steps"]
    runners = [s.get("run", "") for s in steps]
    assert any("check-upstream-shadowing.py" in r for r in runners), (
        "the check must run in the remeasure job, which is gated on upstream "
        "having actually published"
    )
    # After the pull request, so a red shadowing check cannot skip the
    # re-measurement the run exists to propose.
    pr_index = next(i for i, s in enumerate(steps)
                    if "create-pull-request" in str(s.get("uses", "")))
    check_index = next(i for i, s in enumerate(steps)
                       if "check-upstream-shadowing.py" in s.get("run", ""))
    assert check_index > pr_index, (
        "the shadowing check runs before the PR step, so failing it would "
        "skip opening the re-measurement PR"
    )
