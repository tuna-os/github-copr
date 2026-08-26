"""The action-key epoch must not change when history is rewritten.

`package-factory-cell.yml` feeds a git-derived timestamp into the action key
as SOURCE_DATE_EPOCH. It used `%ct` -- the COMMITTER date -- which a commit
object gets afresh on every history rewrite even when the tree is unchanged:
rebase, cherry-pick, `--amend`, and squash-merge (this repo's merge
convention).

Measured on a byte-identical pair: run 32540188656 (fd90915) and run
32541649752 (1e9cdfb) differ only by a `git cherry-pick`, and every quickshell
cell rebuilt from scratch in both -- ~15 minutes per cell, paid twice for the
same bytes. Since a squash-merge rewrites the commit too, the first run on
main after any merge re-derives a fresh epoch for every recipe the PR touched.

`%at` (author date) is preserved by cherry-pick, rebase and amend, so an
unchanged recipe keeps its key. See #477.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELL = ROOT / ".github" / "workflows" / "package-factory-cell.yml"
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow() -> str:
    return CELL.read_text(encoding="utf-8")


def epoch_lines() -> list[str]:
    return [ln.strip() for ln in workflow().splitlines() if "epoch=$(git log" in ln]


def every_epoch_line() -> dict[str, list[str]]:
    """Every workflow that derives an epoch, not just the cell runner.

    This file read one file for its whole life, and that is precisely how the
    bug below survived: #529 removed the manifest from the cell runner's epoch
    and left the publisher's copy of the same line untouched, because nothing
    looked at it.
    """
    found = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        lines = [
            ln.strip()
            for ln in path.read_text(encoding="utf-8").splitlines()
            if "epoch=$(git log" in ln
        ]
        if lines:
            found[path.name] = lines
    return found


def test_both_engines_derive_an_epoch():
    """tideforge and build-chain each have their own derivation; a fix that
    only lands on one leaves the other invalidating on every rewrite."""
    assert len(epoch_lines()) == 2, epoch_lines()


def test_no_epoch_uses_committer_date():
    assert not [ln for ln in epoch_lines() if "%ct" in ln], epoch_lines()


def test_every_epoch_uses_author_date():
    assert all("--format=%at" in ln for ln in epoch_lines()), epoch_lines()


def test_the_epoch_still_reaches_the_action_key():
    """A stable epoch is pointless if it stops being an input -- the key would
    then ignore it entirely rather than track it stably."""
    assert "--source-date-epoch" in workflow()


def test_the_reason_is_recorded_next_to_the_change():
    """%at over %ct looks arbitrary without the rewrite rationale, and the
    obvious 'fix' for a reader is to put %ct back."""
    text = workflow()
    anchor = text.index("--format=%at")
    preamble = text[max(0, anchor - 1200):anchor]
    assert "#477" in preamble
    assert re.search(r"author", preamble, re.I)


# ── The two halves of the nightly→publisher bridge must agree ────────────────
#
# publish-build-chain-rpms.yml resumes the nightly's banked partial, and its
# own comment says the key "must MATCH the nightly's or the bridge is a
# mirage". The epoch is an action-key input, so any difference in how the two
# derive it breaks that match silently — no error, just a chain that restarts
# at bootstrap-00 while every step reports success.
#
# Measured on 2026-08-26, before the fix: manifests/package-factory.yaml last
# moved at 1787654862, the hummingbird sources at 1787527705. The publisher
# included the manifest in its `git log` paths and the nightly (post-#529) did
# not, so they disagreed by 127157 seconds — 35 hours — and had done since
# #529 merged.


def test_no_workflow_puts_the_manifest_in_the_epoch_paths():
    """The manifest is the input #529 removed; it must stay out of all of them."""
    offenders = [
        f"{name}: {line}"
        for name, lines in every_epoch_line().items()
        for line in lines
        if "matrix.manifest" in line
    ]
    assert not offenders, (
        "an epoch derived from the manifest re-keys every cell on any manifest "
        "edit, and disagrees with the cell runner's key: " + "; ".join(offenders)
    )


def test_every_workflow_that_derives_an_epoch_uses_the_same_paths():
    """Guard the guard: equality, not just absence of the manifest.

    Asserting only that the manifest is gone would still pass if one workflow
    added some other path the other lacked — the same class of silent drift
    one input over.
    """
    def paths(line: str) -> str:
        return line.split("--", 1)[1].strip() if "--" in line else line

    seen = {
        name: sorted({paths(line) for line in lines})
        for name, lines in every_epoch_line().items()
    }
    assert seen, "no workflow derives an epoch — this test is measuring nothing"
    native = {
        name: [p for p in ps if "source_paths" in p] for name, ps in seen.items()
    }
    native = {name: ps for name, ps in native.items() if ps}
    assert len(native) >= 2, (
        "expected both the cell runner and the publisher to derive a native "
        f"epoch; found {sorted(native)}"
    )
    distinct = {tuple(ps) for ps in native.values()}
    assert len(distinct) == 1, (
        "the nightly and the publisher derive the epoch from different paths, "
        f"so their action keys cannot match: {native}"
    )


def test_the_publisher_refuses_an_empty_source_path_list():
    """`git log -1 --format=%at --` with no paths returns the repo's last commit.

    That re-keys every cell on every push — strictly worse than the bug this
    fixes, and silent, because an epoch is just a number. The cell runner
    already guards it; the publisher must too.
    """
    body = (WORKFLOWS / "publish-build-chain-rpms.yml").read_text(encoding="utf-8")
    assert "declares no source_paths" in body
    assert '"${#source_paths[@]}" -eq 0' in body
