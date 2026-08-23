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
        "donor_suites": ["stonking", "stonking-proposed"],
        "tiers": [["gtk4"], ["mutter"]],
        "packages": [
            {"source": "gtk4", "donor_version": "4.23.2+ds-1", "depth": 1},
            {"source": "mutter", "donor_version": "51~beta-1", "depth": 0},
        ],
    }
    text = gap.render_build_order("ubuntu", entry, ["mutter"])
    parsed = yaml.safe_load(text)
    assert parsed["target_suite"] == "resolute"
    assert parsed["donor_suites"] == ["stonking", "stonking-proposed"]
    assert parsed["tiers"][0]["packages"][0] == {"source": "gtk4", "version": "4.23.2+ds-1"}
    # Deepest build-dependency first: gtk4 must build before mutter.
    assert parsed["tiers"][1]["packages"][0]["source"] == "mutter"
    assert text.startswith("# GENERATED"), "a generated file must say so"


def test_the_mounted_output_path_is_absolute():
    """docker reads a RELATIVE --volume source as a NAMED VOLUME.

    The first real dispatch (run 32641183871) died on exactly this, and the
    error blames the wrong thing -- it complains about invalid characters in a
    volume name rather than saying the path was relative:

        docker: Error response from daemon: create .factory/backport-ubuntu:
        ".factory/backport-ubuntu" includes invalid characters for a local
        volume name, only "[a-zA-Z0-9][a-zA-Z0-9_.-]" are allowed.

    Everything before it worked: the measurement ran, --tier narrowed the order
    to 2 source packages, and the image pulled. Resolved inside the script so
    every caller is covered rather than only the workflow that hit it.
    """
    text = chain_text()
    resolve = text.index('out=$(cd "$out" && pwd)')
    mount = text.index('--volume "$out:/work"')
    assert resolve < mount, "the output path must be absolute before it is mounted"


def test_every_donor_suite_gets_its_own_deb_src_line():
    """Ubuntu needs the release pocket AND -proposed: an in-flight transition
    can leave a source unbuildable from the release pocket alone."""
    text = chain_text()
    assert "for donor_suite in $DONOR_SUITES" in text
    assert "DONOR_SUITES=" in text
    # Still sources only, per suite.
    assert 'printf "deb-src %s %s %s\\n"' in text


def _report_entry_keys() -> set[str]:
    """The keys measure-deb-backport-gap.py actually writes per target.

    Read out of the source rather than by running a measurement, because a
    measurement needs the network. The assignment is
    `report["targets"][name] = { ... }`, a dict of literal string keys.
    """
    import ast

    tree = ast.parse((ROOT / "scripts" / "measure-deb-backport-gap.py").read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Subscript):
            continue
        inner = target.value
        if not (isinstance(inner, ast.Subscript) and isinstance(inner.value, ast.Name)
                and inner.value.id == "report"):
            continue
        return {
            key.value for key in node.value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
    raise AssertionError("could not find the `report['targets'][name] = {...}` assignment")


def test_the_workflow_summary_only_reads_keys_the_report_emits():
    """A field rename in the script must not leave the workflow reading a
    key that no longer exists.

    This is not hypothetical. `donor_suite` became `donor_suites` when Ubuntu
    gained a second donor pocket; the script, manifest and tests were all
    renamed together, and the workflow's inline step-summary snippet was not.
    Run 32650470179 measured the gap correctly -- the log carries
    `resolute <- stonking + stonking-proposed: 17 source packages, 4 tiers` --
    and then died 16 seconds in with `KeyError: 'donor_suite'` while printing
    that same sentence to the summary.

    The measurement is the expensive part and it had already succeeded. Losing
    a run to a typo'd key in the cosmetic step after it is the kind of failure
    a test costs nothing to prevent, so: whatever the workflow reads off an
    entry must be something the script puts there.
    """
    emitted = _report_entry_keys()
    assert "donor_suites" in emitted, "sanity: the renamed key is the one in use"
    read = set(re.findall(r"entry\[['\"]([A-Za-z_]+)['\"]\]", WORKFLOW.read_text()))
    assert read, "the workflow is expected to read fields off the report entry"
    unknown = read - emitted
    assert not unknown, (
        f"the workflow reads report fields the script does not emit: {sorted(unknown)}; "
        f"emitted keys are {sorted(emitted)}"
    )


def test_the_tier_input_is_documented_as_narrowing_not_resuming():
    """`--tier` selects a subset of ONE run; it cannot continue a previous one.

    The local apt repo that carries a tier's output to the next tier lives on
    the runner and dies with the job. So dispatching tier-1 after a tier-0 run
    resolves tier-1's build-deps against the target archive alone -- and that
    does not fail loudly. It builds, and produces packages linked against the
    versions the backport exists to replace.

    The workflow used to advise exactly that ("re-dispatch with --tier") as
    the remedy for hitting the timeout, which is the most likely moment for
    someone to follow it.
    """
    text = WORKFLOW.read_text()
    assert "it cannot resume one" in text
    assert "RE-DISPATCH FROM tier-0 OR WITH NO TIER" in text
    # The input's own description already says empty builds everything.
    workflow = yaml.safe_load(text)
    # PyYAML reads a bare `on:` key as the boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert "empty builds all" in triggers["workflow_dispatch"]["inputs"]["tier"]["description"]


def test_the_buildroot_has_a_usable_utf8_locale():
    """A buildroot should have locale data; a minimal Ubuntu image has none.

    That is worth doing on its own terms. It is NOT, on the evidence, the
    cause of the gnome-desktop:languages SIGABRT it was added to explain:
    run 32659338235 generated the locales and the failure is unchanged, with
    `is_utf8: FALSE` still printed by the same suite. The diagnosis was wrong;
    the change is kept because the buildroot is better with it, not because it
    fixed the thing it was aimed at.

    Exporting the variable is not the same as having the locale, which is why
    the assertion below is the load-bearing half.
    """
    text = chain_text()
    assert "locales" in text, "the locales package must be installed"
    assert "locale-gen C.UTF-8" in text
    install = text.index("build-essential devscripts dpkg-dev ca-certificates")
    generate = text.index("locale-gen C.UTF-8")
    build = text.index("apt-get build-dep")
    assert install < generate < build, (
        "the locale must exist before any package is built against it"
    )


def test_the_locale_assertion_checks_a_locale_that_had_to_be_generated():
    """The first version of this check could not fail.

    It asked `LC_ALL=C.UTF-8 locale charmap`, and C.UTF-8 is built into glibc
    -- it resolves with zero generated locales, so the assertion would have
    passed on the very image it was written to catch. en_US.UTF-8 exists only
    if locale-gen actually ran.

    An assertion that cannot fail is worse than no assertion: it reports a
    property nobody has checked.
    """
    text = chain_text()
    # The assignment, not the prose: the comment above it legitimately quotes
    # the old form to explain why it was wrong.
    assert "charmap=$(LC_ALL=en_US.UTF-8 locale charmap" in text
    assert "charmap=$(LC_ALL=C.UTF-8 locale charmap" not in text
    assert "locale-gen did not produce a usable UTF-8 locale" in text


def test_a_failing_test_suite_surfaces_its_own_log():
    """meson prints a summary line and buffers the output elsewhere.

        4/6 gnome-desktop:languages  FAIL  (exit status 134 or signal 6 SIGABRT)

    That names the test and says nothing about why. The real output goes to
    meson-logs/testlog*.txt inside the build tree, which is not uploaded --
    so two full chain runs, 1h47m each, were spent guessing at a cause the log
    could not confirm. Copy it out and print it.
    """
    text = chain_text()
    assert "testlog*.txt" in text
    assert "test-suite.log" in text, "autotools buffers the same way"
    assert "/work/logs/$source.$(basename" in text, "and it must survive the run"


def test_the_chain_body_carries_no_apostrophes():
    """The docker body is a single-quoted `bash -lc` string.

    ONE apostrophe ends it early, and bash then reports `unexpected EOF while
    looking for matching '` at the LAST line of the script -- nowhere near the
    comment that broke it. The word that did it while writing the locale fix
    above was "Ubuntu's".

    verify-package-factory-cell.sh has the same shape and the same guard.
    """
    text = chain_text()
    start = text.index("bash -lc '")
    body = text[start + len("bash -lc '"):]
    end = body.index("\n  '")
    assert "'" not in body[:end], (
        "an apostrophe inside the single-quoted bash -lc body ends it early; "
        "bash will report the error at the end of the file, not here"
    )


def test_the_container_image_file_exclusions_are_lifted_first():
    """A container image is not a chroot, and the difference is measurable.

    Ubuntu images ship /etc/dpkg/dpkg.cfg.d/excludes to drop translation
    catalogues and manpages. Correct for a runtime image, wrong for a
    buildroot -- the Ubuntu builders use sbuild chroots, which are full
    installs.

    What it cost, from run 32665378407 once the chain surfaced the meson
    testlog:

        # Ignoring `C.UTF-8` as a locale, since it lacks translations
        # Ignoring `en_US.UTF-8` as a locale, since it lacks translations
        not ok /languages/using-null-locale - GnomeDesktop-FATAL-WARNING:
          Could not read list of available locales from libc ...
        Bail out!

    The locales were there. Every one was discarded for having no
    translations, the list came out empty, and glib made the warning fatal.

    ORDER IS THE PROPERTY. dpkg applies exclusions at unpack time, so
    anything installed before the file is removed keeps its files stripped.
    """
    text = chain_text()
    assert "rm -f /etc/dpkg/dpkg.cfg.d/excludes" in text
    lift = text.index("rm -f /etc/dpkg/dpkg.cfg.d/excludes")
    install = text.index("build-essential devscripts dpkg-dev ca-certificates")
    assert lift < install, (
        "exclusions must be lifted before any package is installed, or dpkg "
        "strips that package regardless"
    )


def test_the_buildroot_proves_it_has_translations_not_just_a_charmap():
    """Checking the charmap alone would pass on the broken buildroot.

    en_US.UTF-8 resolved fine in run 32665378407 -- `locale charmap` said
    UTF-8 -- and gnome-desktop still discarded it, because a locale with no
    message catalogue is not a locale as far as that code is concerned. The
    assertion has to look for the catalogues.
    """
    text = chain_text()
    assert "no translation catalogues" in text
    assert "*.mo" in text
