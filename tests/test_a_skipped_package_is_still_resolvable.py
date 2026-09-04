"""A cell may only skip what its buildroot can resolve.

build-chain.sh skips a package when the published index already serves its
NVR -- "Skipping: <nvr> already served by the published index" -- on the
stated ground that "consumers resolve it from the repo at priority 11". That
holds only if the index is declared as a repo in the mock config the cell
builds with. When it is not, a skipped package is in neither [local-build]
nor any remote repo, and the first tier that BuildRequires it fails on a
dependency the factory had already built.

Run 33835533548 is the measurement. gnome50-el10-x86_64 built with the
generic centos-stream-10-ci config, which declares the XFCE family's index
and not GNOME 50's. glib2-2.88.0-4.el10 was skipped as already served; gtk4
then died on "No matching package to install: 'pkgconfig(glib-2.0) >=
2.84.0'" and pango on 'pkgconfig(pango) >= 1.56.0', 64 minutes in.

So: every cell whose family publishes to an r2_path must build with a mock
config that declares that same published prefix.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "manifests" / "package-builds.yaml"
MOCK = ROOT / "mock"

PUBLISHED = "https://repo.tunaos.org/"


def cells() -> list[dict]:
    doc = yaml.safe_load(CATALOG.read_text())
    return [c for c in doc["native_builds"] if isinstance(c, dict)]


def baseurls(cfg: Path) -> set[str]:
    return set(re.findall(r"^baseurl=(\S+)", cfg.read_text(), flags=re.M))


# Cells that still violate the rule. Every one of them can lose a tier the
# same way gnome50 did, the moment its prefix serves an NVR the chain would
# otherwise build. They are listed rather than fixed here because each needs
# its own prefix checked against a real published index, and this change is
# scoped to the family that actually failed (tunaos-packages#682).
#
# This list may only SHRINK. A new violator is a new outage waiting on a
# publish, so it fails below rather than joining the list.
KNOWN_GAPS = {
    "gnome50-el10-aarch64",
    "xfce-el10-aarch64",
    "xfce-fedora-x86_64",
    "xfce-fedora-aarch64",
    "hummingbird-x86_64",
    "hummingbird-aarch64",
    "fprintd-el10-aarch64",
}


def violators() -> set[str]:
    bad = set()
    for cell in cells():
        r2_path, mock_config = cell.get("r2_path"), cell.get("mock_config")
        if not r2_path or not mock_config:
            continue
        cfg = MOCK / f"{mock_config}.cfg"
        if not cfg.is_file():
            bad.add(cell["id"])
            continue
        want = f"{PUBLISHED}{r2_path.rstrip('/')}/"
        have = {u.rstrip("/") + "/" for u in baseurls(cfg) if u.startswith(PUBLISHED)}
        if want not in have:
            bad.add(cell["id"])
    return bad


def test_no_cell_outside_the_known_gaps_builds_blind_to_its_own_index():
    new_violators = violators() - KNOWN_GAPS
    assert not new_violators, (
        f"{sorted(new_violators)} publish to a prefix their mock config does not "
        "declare. build-chain.sh skips whatever that prefix already serves, so a "
        "skipped package would sit in no repo the buildroot can see and the first "
        "tier that BuildRequires it fails."
    )


def test_the_known_gap_list_only_shrinks():
    fixed = KNOWN_GAPS - violators()
    assert not fixed, (
        f"{sorted(fixed)} no longer violate the rule — delete them from KNOWN_GAPS "
        "so the list keeps meaning what it says"
    )


def test_every_named_gap_is_a_real_cell():
    ids = {c.get("id") for c in cells()}
    assert KNOWN_GAPS <= ids, f"KNOWN_GAPS names cells that do not exist: {sorted(KNOWN_GAPS - ids)}"


def test_the_family_that_failed_is_fixed():
    """gnome50-el10-x86_64 is the cell run 33835533548 died on; it must not be
    in the gap list, and its config must name its own prefix."""
    assert "gnome50-el10-x86_64" not in violators()
    cell = next(c for c in cells() if c["id"] == "gnome50-el10-x86_64")
    assert cell["mock_config"] == "centos-stream-10-ci-gnome50"
    cfg = (MOCK / f"{cell['mock_config']}.cfg").read_text()
    assert "[tunaos-gnome50]" in cfg
    assert not [u for u in baseurls(MOCK / f"{cell['mock_config']}.cfg")
                if "copr" in u], (
        "no COPR baseurl in a GNOME 50 buildroot (maintainer directive "
        "2026-09-03: nothing below 50 ships, and no COPR is a source)"
    )


def test_the_skip_still_justifies_itself_by_the_buildroot():
    """If the skip stops citing the buildroot, the test above stops meaning
    what it says. Keep them tied together."""
    src = (ROOT / "scripts" / "build-chain.sh").read_text()
    assert "already served by the published index" in src
    assert "SERVED_NVRS_SET" in src
