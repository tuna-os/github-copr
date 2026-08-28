"""One wall at the bottom of a tier is one blocker, not eight.

The 2026-08-28 GNOME 51 wave reported eight failed packages:

    gtk4, libadwaita, mutter, gnome-shell, nautilus,
    xdg-desktop-portal-gnome, gnome-control-center, gnome-initial-setup

There was one failure. gtk4 could not build against pango 1.57, and the other
seven build against gtk4 or mutter-devel and never had a chance. Establishing
that took a human twenty minutes and three log fetches, and it is the shape
every wave takes: a wall, and a fan of dependents above it.

That distinction decides everything downstream. Eight blockers is a list
nobody can triage and an agent fleet would fan out over, seven of them fixing
nothing. One blocker with seven dependents is a single piece of work.

What these pin:

  CASCADE     the seven are attributed to gtk4, from their own logs;
  NO GUESS    a package with no evidence is `unclassified` or `not-reached`,
              never assigned a cause. This factory has already asserted a
              changelog error as python-aiohappyeyeballs's cause from log-line
              proximity, and been wrong; a classifier that always answers
              would make that mistake at scale.
  THE CLASSES each named class is pinned by the real failure that named it,
              so renaming or reordering the table cannot silently reclassify
              a wave.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "classify-chain-failures.py"

_spec = importlib.util.spec_from_file_location("classify", SCRIPT)
classify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(classify)

GNOME51_SUMMARY = """
Tiers processed: 17     Packages built: 55
ERROR: Failed packages (8):
  - src/gnome-51/gtk4
  - src/gnome-51/libadwaita
  - src/gnome-51/mutter
  - src/gnome-51/gnome-shell
  - src/gnome-51/nautilus
  - src/gnome-51/xdg-desktop-portal-gnome
  - src/gnome-51/gnome-control-center
  - src/gnome-51/gnome-initial-setup
"""

DEPENDENTS = [
    "libadwaita", "mutter", "nautilus", "xdg-desktop-portal-gnome",
    "gnome-control-center", "gnome-initial-setup",
]


@pytest.fixture()
def gnome51_logs(tmp_path: pathlib.Path) -> pathlib.Path:
    logs = tmp_path / "failure-logs"
    logs.mkdir()
    (logs / "gtk4.build.log").write_text(
        "../subprojects/pango/pango/pango-item.c:120:5: error: implicit "
        "declaration [-Werror=implicit-function-declaration]\n"
        "Bad exit status from /var/tmp/rpm-tmp.aBcDeF (%build)\n"
    )
    for name in DEPENDENTS:
        (logs / f"{name}.root.log").write_text(
            "Problem: conflicting requests\n"
            f"  - nothing provides pkgconfig(gtk4) >= 4.23 needed by "
            f"{name}-51.0-1.fc43.src\n"
        )
    # The eighth names the dependency by its -devel subpackage instead of a
    # pkgconfig capability. Both spellings appear in real root.logs, and a
    # cascade check that only understood one would split the wave in two.
    (logs / "gnome-shell.root.log").write_text(
        "Problem: nothing provides gtk4-devel >= 4.23 needed by gnome-shell\n"
    )
    return logs


def test_the_wave_is_one_blocker_and_seven_dependents(gnome51_logs) -> None:
    report = classify.analyse(GNOME51_SUMMARY, gnome51_logs)
    assert report["failed"] == 8
    assert report["blockers"] == 1, [
        r["package"] for r in report["records"] if r["kind"] == "root"
    ]
    assert report["dependents"] == 7
    root = next(r for r in report["records"] if r["kind"] == "root")
    assert root["package"] == "gtk4"
    assert set(root["dependents"]) == set(DEPENDENTS) | {"gnome-shell"}


def test_a_dependent_names_what_it_is_waiting_for(gnome51_logs) -> None:
    report = classify.analyse(GNOME51_SUMMARY, gnome51_logs)
    for record in report["records"]:
        if record["kind"] == "cascade":
            assert record["blocked_by"] == "gtk4", record


def test_the_root_is_not_attributed_to_its_own_dependents(gnome51_logs) -> None:
    """gtk4's log names pango, and pango did not fail; nothing may loop."""
    report = classify.analyse(GNOME51_SUMMARY, gnome51_logs)
    for record in report["records"]:
        assert record["blocked_by"] != record["package"], record


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "Temporary repodata directory /x/.repodata/ already exists! "
            "(Another createrepo process is running?)",
            "chain-infra",
        ),
        ("error: %changelog not in descending order", "spec-changelog"),
        ("2 out of 5 hunks FAILED -- saving rejects", "patch-rejected"),
        (
            "package foo requires bar >= 2, but none of the providers can be "
            "installed",
            "version-blocked",
        ),
        ("Problem: nothing provides libdrm-devel", "unsatisfied-buildrequires"),
        ("ERROR: No RPMs produced for zxing-cpp", "no-output"),
        ("Bad exit status from /var/tmp/rpm-tmp.x (%build)", "compile-error"),
        ("the runner exploded in an entirely novel way", "unclassified"),
    ],
)
def test_each_class_is_pinned_by_the_failure_that_named_it(
    text: str, expected: str
) -> None:
    assert classify.classify(text)[0] == expected


def test_a_test_only_buildrequires_is_its_own_class(
    tmp_path: pathlib.Path,
) -> None:
    """The chain passes --without check; on a spec with no %bcond that is inert.

    python-aiohappyeyeballs's Fedora spec carries
    `BuildRequires: %{py3_dist pytest-asyncio}` unconditionally, so no builder
    flag can drop it and the fix is a packaging decision. Reporting it as an
    ordinary missing dependency sends whoever picks it up looking for a
    repository to add, which is not the answer.
    """
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "python-aiohappyeyeballs.root.log").write_text(
        "Problem: package python3-pytest-asyncio requires "
        "python3.14dist(pytest) < 9\n"
        "  - nothing provides python3.14dist(pytest-asyncio) needed by "
        "python-aiohappyeyeballs\n"
    )
    report = classify.analyse_names(["python-aiohappyeyeballs"], logs)
    record = report["records"][0]
    assert record["class"] == "unconditional-test-buildrequires"
    assert "%bcond" in record["why"]


def test_a_package_with_no_log_is_not_given_a_cause(
    tmp_path: pathlib.Path,
) -> None:
    """An unreached package is work the wave ran out of clock for."""
    logs = tmp_path / "logs"
    logs.mkdir()
    report = classify.analyse_names(["never-reached"], logs)
    record = report["records"][0]
    assert record["class"] == "not-reached"
    assert record["evidence"] == ""


def test_the_residue_can_come_from_the_index_rather_than_a_log(
    tmp_path: pathlib.Path,
) -> None:
    """`--packages` is the convergence loop's list of unserved packages.

    Preferred over scraping "Failed packages" out of a job log: a failure
    whose line scrolled past a truncated tail is still in the residue, and so
    is a package no shard ever reached -- which a log scraper cannot see.
    """
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "gtk4.build.log").write_text("Bad exit status from rpm-tmp (%build)")
    (logs / "mutter.root.log").write_text(
        "nothing provides pkgconfig(gtk4) >= 4.23 needed by mutter"
    )
    report = classify.analyse_names(["gtk4", "mutter", "unreached"], logs)
    kinds = {r["package"]: (r["kind"], r["class"]) for r in report["records"]}
    assert kinds["gtk4"] == ("root", "compile-error")
    assert kinds["mutter"][0] == "cascade"
    assert kinds["unreached"] == ("root", "not-reached")


def test_the_rendered_report_names_the_blocker_and_its_dependents(
    gnome51_logs,
) -> None:
    text = classify.render(classify.analyse(GNOME51_SUMMARY, gnome51_logs))
    assert "1 blocker(s), 7 dependent(s)" in text
    assert "### gtk4" in text
    for name in DEPENDENTS:
        assert f"`{name}`" in text
        # A dependent must not get a section of its own -- that is the
        # eight-bugs reading this exists to prevent.
        assert f"### {name}" not in text


def test_a_longer_name_is_not_swallowed_by_a_failed_prefix(
    tmp_path: pathlib.Path,
) -> None:
    """`gtk4-layer-shell` is not `gtk4`, and `-` is a regex word boundary.

    Without an explicit end-of-name check, a package waiting on
    gtk4-layer-shell reads as a dependent of a failed gtk4 it has nothing to
    do with: the blocker it actually needs is never raised, and an agent sent
    to fix gtk4 makes no difference to it.
    """
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "gtk4.build.log").write_text("Bad exit status from rpm-tmp (%build)")
    (logs / "waybar.root.log").write_text(
        "Problem: nothing provides gtk4-layer-shell-devel needed by waybar\n"
    )
    report = classify.analyse_names(["gtk4", "waybar"], logs)
    waybar = next(r for r in report["records"] if r["package"] == "waybar")
    assert waybar["blocked_by"] != "gtk4", (
        "waybar waits on gtk4-layer-shell, a different source package"
    )
    assert waybar["kind"] == "root"


def test_a_subpackage_still_counts_as_its_source(tmp_path: pathlib.Path) -> None:
    """The lookahead must not lose the spelling a real BuildRequires uses."""
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "gtk4.build.log").write_text("Bad exit status from rpm-tmp (%build)")
    for spelling in ("gtk4-devel >= 4.23", "pkgconfig(gtk4) >= 4.23", "gtk4"):
        (logs / "mutter.root.log").write_text(
            f"Problem: nothing provides {spelling} needed by mutter\n"
        )
        report = classify.analyse_names(["gtk4", "mutter"], logs)
        mutter = next(r for r in report["records"] if r["package"] == "mutter")
        assert mutter["blocked_by"] == "gtk4", spelling
