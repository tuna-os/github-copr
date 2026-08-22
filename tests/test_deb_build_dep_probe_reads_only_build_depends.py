"""The build-dep probe must list build-dependencies, and nothing else.

The probe prints each declared build-dep's apt candidate so an unsatisfiable
one is named in the job that fails, instead of being buried in `apt-get
build-dep`'s cascade of "but it is not going to be installed" lines. That
only works if the column is trustworthy.

It was not. The extraction ran from `Build-Depends:` to the next BLANK line,
but in deb822 the source stanza continues past Build-Depends into the fields
that follow it -- the blank line does not come until the first binary
package stanza. So `Standards-Version: 4.6.2` and `Rules-Requires-Root: no`
were fed to `apt-cache policy` as if they were package names and printed as
NOT AVAILABLE. Two guaranteed false alarms in a column whose entire job is
to make a real NOT AVAILABLE stand out.

A field's continuation lines are the ones beginning with whitespace, so that
-- not the blank line -- is where the value ends.

These tests EXECUTE the extraction lifted out of the runner rather than
matching its text, so they measure behaviour and cannot pass on a pipeline
that no longer works.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run-package-factory-cell.sh"


def extraction() -> str:
    """The awk|tr|sed|grep pipeline, lifted verbatim from the runner.

    Derived from the script so the tests cannot drift away from what ships:
    if the pipeline is edited, these run against the edit.
    """
    text = RUNNER.read_text(encoding="utf-8")
    start = text.index('awk "/^Build-Depends:/')
    end = text.index('| while read -r dep;', start)
    pipeline = text[start:end]
    # Drop the line continuations; the runner writes it across four lines.
    pipeline = pipeline.replace("\\\n", " ")
    # It reads a fixed relative path; the tests supply their own file.
    return pipeline.replace("debian/control", '"$1"')


def probe(control: str, tmp_path: Path) -> list[str]:
    ctl = tmp_path / "control"
    ctl.write_text(control, encoding="utf-8")
    out = subprocess.run(
        ["bash", "-c", extraction(), "_", str(ctl)],
        capture_output=True, text=True, check=True,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


CONTROL = """Source: cpptrace-devel
Section: libdevel
Priority: optional
Maintainer: TunaOS <ci@tunaos.org>
Build-Depends: debhelper-compat (= 13),
               cmake,
               libzstd-dev,
               libdwarf-dev
Standards-Version: 4.6.2
Rules-Requires-Root: no

Package: libcpptrace-dev
Architecture: any
Depends: ${misc:Depends}
Description: stacktrace library
"""


def test_it_lists_exactly_the_build_dependencies(tmp_path):
    assert probe(CONTROL, tmp_path) == ["cmake", "libzstd-dev", "libdwarf-dev"]


def test_the_fields_after_build_depends_are_not_probed(tmp_path):
    """The regression itself: these are deb822 fields, not packages, and
    every one of them printed NOT AVAILABLE."""
    got = probe(CONTROL, tmp_path)
    assert not [d for d in got if "Standards-Version" in d or "Rules-Requires-Root" in d]


def test_no_probed_name_is_a_deb822_field(tmp_path):
    """Stated as a property rather than a list, so a control file carrying
    some other trailing field (Homepage, Vcs-Git, Testsuite) cannot
    reintroduce the same class of noise unnoticed."""
    for dep in probe(CONTROL, tmp_path):
        assert not re.match(r"^[A-Za-z][A-Za-z0-9-]*:", dep), dep


def test_a_binary_stanza_depends_is_never_read(tmp_path):
    """Build-Depends can be the last field of the source stanza. The binary
    stanza's own Depends is a runtime dependency and must not be probed."""
    control = (
        "Source: x\nStandards-Version: 4.6.2\n"
        "Build-Depends: cmake,\n               ninja-build\n"
        "\nPackage: y\nDepends: runtime-only-not-a-builddep\n"
    )
    assert probe(control, tmp_path) == ["cmake", "ninja-build"]


def test_a_single_line_build_depends_still_works(tmp_path):
    """Most recipes render it on one line with no continuations at all."""
    control = (
        "Source: x\n"
        "Build-Depends: debhelper-compat (= 13), cmake, ninja-build\n"
        "Standards-Version: 4.6.2\n\nPackage: y\n"
    )
    assert probe(control, tmp_path) == ["cmake", "ninja-build"]


def test_version_constraints_are_stripped(tmp_path):
    """`apt-cache policy 'qt6-base-dev (>= 6.8)'` finds nothing; the probe
    must ask about the package, not the dependency expression."""
    control = (
        "Source: x\n"
        "Build-Depends: qt6-base-dev (>= 6.8), libwayland-dev (>= 1.41)\n"
        "\nPackage: y\n"
    )
    assert probe(control, tmp_path) == ["qt6-base-dev", "libwayland-dev"]


def test_debhelper_compat_is_still_excluded(tmp_path):
    """It is a build-profile token, not an installable package. Guarded here
    against the extraction change as well as against the grep being edited."""
    assert "debhelper-compat" not in probe(CONTROL, tmp_path)
