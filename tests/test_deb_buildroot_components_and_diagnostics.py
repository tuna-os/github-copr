"""The deb buildroot must not inherit whatever apt components the base ships.

Ubuntu keeps a large share of Debian-synced packages in `universe`.
quickshell needs two of them (libcli11-dev, libcpptrace-dev), and the ubuntu
cell reported `libcpptrace-dev but it is not installable ... [no choices]`
while the same packages installed cleanly on Debian sid in the same run
(32541649752). Pinning the components makes the buildroot independent of the
base image's defaults; on Debian there is no ubuntu.sources and no such
component, so it is a no-op.

The diagnostic exists because `apt-get build-dep` reports an unsatisfiable
dependency as a cascade: one genuinely missing package produces a dozen
"but it is not going to be installed" lines for packages that are fine. That
cost a whole run to interpret, twice. Printing each declared build-dep's
candidate version first names the real one in the same job that fails.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run-package-factory-cell.sh"


def deb_block() -> str:
    text = RUNNER.read_text(encoding="utf-8")
    start = text.index("  deb)")
    return text[start:text.index("  pkg.tar.zst)", start)]


def test_the_deb_buildroot_pins_apt_components():
    assert "Components: main restricted universe multiverse" in deb_block()


def test_components_are_pinned_before_apt_update():
    """Rewriting sources after `apt-get update` leaves the old index in place,
    so the new component is invisible for this build."""
    block = deb_block()
    assert block.index("Components:") < block.index("apt-get update")


def test_it_edits_only_ubuntus_sources_file():
    """Debian has no universe; guarding on ubuntu.sources keeps this a no-op
    there rather than corrupting a Debian buildroot's sources."""
    block = deb_block()
    assert "/etc/apt/sources.list.d/ubuntu.sources" in block
    assert "if [ -f /etc/apt/sources.list.d/ubuntu.sources ]" in block


def test_build_dep_availability_is_printed_before_resolution():
    block = deb_block()
    assert "build-dependency availability" in block
    # Match the invocation, not the prose: "apt-get build-dep" also appears in
    # the comment explaining why this probe exists, and that comment sits
    # ABOVE the probe.
    assert block.index("build-dependency availability") < block.index("apt-get build-dep -y")


def test_a_missing_dependency_is_labelled_not_available():
    """Without an explicit label a missing candidate prints as an empty column
    and reads like a formatting glitch rather than the answer."""
    assert "NOT AVAILABLE" in deb_block()


def test_debhelper_compat_is_excluded_from_the_probe():
    """It is a build-profile token, not an installable package; probing it
    would always print NOT AVAILABLE and train readers to ignore the column."""
    assert "debhelper-compat" in deb_block()
