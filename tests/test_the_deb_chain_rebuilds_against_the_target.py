"""The deb backport engine, and the two ways it could silently be wrong.

scripts/build-deb-chain.sh is the deb twin of build-chain.sh: it walks a
measured order tier by tier, rebuilding each donor-suite source package in a
TARGET-suite buildroot, accumulating results into a local apt repo so a tier
can resolve what the previous one produced.

Two properties are load-bearing, and both fail quietly rather than loudly.

1. THE DONOR MUST BE `deb-src` ONLY, NEVER `deb`.
   A binary `deb` line for the donor suite would let apt satisfy build
   dependencies from the donor. Everything would still compile and the run
   would go green -- but the packages would be linked against the donor's
   libraries and would not install on the target, because their shared-library
   dependencies resolve to versions the target does not have. That is not a
   backport; it is the donor suite with extra steps. `deb-src` carries no
   binaries and cannot do this.

2. THE LOCAL REPO MUST NOT BE PINNED ABOVE THE TARGET ARCHIVE.
   Every package the chain builds is NEWER than the target's, so apt prefers
   it at equal priority and no pin is needed. Pinning above 500 would also let
   the local repo outrank the archive for packages the chain did NOT build --
   the failure the rpm path hit at priority=999, where a served package
   outranked and replaced a base one (the glib2 Obsoletes incident, publish
   run 32405815822).

Separately: the generated order must stay OUT of the `build-order*.yml`
namespace. Two consumers glob that pattern and expect the rpm shape, where a
package is a `path` to a spec directory in this repository. A backport has no
such path -- its packaging lives in the donor suite -- so it uses `source` and
`version` instead. scripts/build-catalog.py does not skip what it cannot
understand: it looks the file's `target` up in TARGET_MAP and calls sys.exit(1)
when there is no entry, so a deb order committed under that name would hard-
fail the RFC 011 catalog builder rather than be ignored.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHAIN = ROOT / "scripts" / "build-deb-chain.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "backport-deb-chain.yml"

_spec = importlib.util.spec_from_file_location(
    "measure_deb_backport_gap", ROOT / "scripts" / "measure-deb-backport-gap.py"
)
gap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gap)


def chain_text() -> str:
    return CHAIN.read_text(encoding="utf-8")


def test_the_donor_is_added_as_sources_only():
    """Every apt line that mentions the donor must be deb-src.

    Binary `deb` lines are legitimate elsewhere -- the accumulating local repo
    is one -- so the rule is not "no deb lines", it is "no deb line that points
    at the donor".
    """
    text = chain_text()
    printf_lines = [l.strip() for l in text.splitlines() if 'printf "deb' in l]
    assert printf_lines, "expected the script to write apt source lines"

    donor_lines = [l for l in printf_lines if "DONOR_SUITE" in l or "donor_url" in l]
    assert donor_lines, "expected the donor suite to be added as a source"
    for line in donor_lines:
        assert 'printf "deb-src' in line, (
            f"a binary deb line for the donor would build the chain against "
            f"the donor suite, producing packages that install nowhere on the "
            f"target: {line}"
        )

    # The local repo is the only binary source the chain adds, and it is local.
    binary_lines = [l for l in printf_lines if 'printf "deb ' in l or 'printf "deb [' in l]
    for line in binary_lines:
        assert "file:///work/repo" in line, line


def test_the_local_repo_is_not_pinned_above_the_archive():
    text = chain_text()
    assert "chain-local.list" in text
    # No preferences file, and no Pin-Priority at all, for the chain repo.
    assert "preferences.d" not in text, (
        "the chain repo needs no pin: its packages are newer, so apt prefers "
        "them anyway, and a pin would let it outrank the archive for packages "
        "the chain did not build"
    )
    assert "Pin-Priority" not in text


def test_the_chain_reindexes_between_packages():
    """Without this a tier cannot resolve what the previous tier built, and
    the ordering the measurement computed would buy nothing."""
    text = chain_text()
    assert "dpkg-scanpackages" in text
    scan = text.index("dpkg-scanpackages")
    assert "apt-get update" in text[scan:scan + 400], (
        "re-indexing without an apt-get update leaves the new package invisible"
    )


def test_the_workflow_regenerates_the_order_rather_than_trusting_the_commit():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "--build-order" in text
    assert "measure-deb-backport-gap.py" in text
    # Dispatch-only: a chain rebuild is hours of runner time.
    assert "workflow_dispatch" in text
    assert "on:\n  push" not in text
    assert "timeout-minutes: 360" in text


def test_an_empty_order_is_not_a_failure():
    """A target that has caught up is the engine working, not breaking."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "nothing to rebuild" in text
    assert "steps.empty.outputs.count != '0'" in text


def test_the_generated_order_stays_out_of_the_build_order_namespace():
    """build-catalog.py sys.exit(1)s on a target it has no TARGET_MAP entry
    for, so a deb order named build-order-*.yml hard-fails it."""
    for path in ROOT.glob("build-order*.yml"):
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for tier in spec.get("tiers") or []:
            for package in tier.get("packages") or []:
                assert "source" not in package or "path" in package, (
                    f"{path.name} carries the deb backport shape; the rpm "
                    f"consumers of build-order*.yml expect `path`"
                )
    # And the workflow must not write one into that namespace either.
    assert "--build-order 'build-order" not in WORKFLOW.read_text(encoding="utf-8")


def test_the_rendered_order_names_sources_and_exact_versions():
    entry = {
        "target_suite": "resolute",
        "donor_suite": "stonking",
        "tiers": [["gtk4"], ["mutter"]],
        "packages": [
            {"source": "gtk4", "donor_version": "4.23.2+ds-1", "depth": 1},
            {"source": "mutter", "donor_version": "51~beta-1", "depth": 0},
        ],
    }
    text = gap.render_build_order("ubuntu", entry, ["mutter"])
    parsed = yaml.safe_load(text)
    assert parsed["target_suite"] == "resolute"
    assert parsed["donor_suite"] == "stonking"
    assert parsed["tiers"][0]["packages"][0] == {"source": "gtk4", "version": "4.23.2+ds-1"}
    # Deepest build-dependency first: gtk4 must build before mutter.
    assert parsed["tiers"][1]["packages"][0]["source"] == "mutter"
    assert text.startswith("# GENERATED"), "a generated file must say so"
