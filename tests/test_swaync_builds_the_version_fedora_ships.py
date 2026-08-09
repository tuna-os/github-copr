"""niri's notification daemon could not build, and Fedora's cannot either.

SwayNotificationCenter is a declared niri root. Importing it from Rawhide
dist-git gets a spec at 0.12.6 whose src/meson.build carries

    dependency('granite-7', version: '>= 7.5.0')

and Rawhide ships Granite 6 -- one `granite` source package providing
pkgconfig(granite) and libgranite.so.6, nothing newer. That is not a
Hummingbird problem: Fedora's own changelog stops at 0.10.1-5 and the binary
in Rawhide today is 0.10.1, so the 0.12.6 bump has never built there. Three
Rawhide packages want granite-7 (SwayNotificationCenter, minder, warble).

Packaging Granite 7 is the better long-term answer -- 0.12.6 is the GTK4 and
libadwaita version, and the rest of niri's stack is GTK4. It is not the answer
available right now: it needs an upstream tarball and its checksum, and the
elementary/granite archive is not reachable from the build environment.

So this pins the version Fedora actually ships. 0.10.1 needs granite 6,
gtk+-3.0, libhandy-1 and gtk-layer-shell-0, all of which Rawhide provides --
all 18 of its BuildRequires resolve. niri gets the same notification daemon a
Fedora user gets today, instead of none.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
VENDORED = REPO / "src" / "hummingbird" / "SwayNotificationCenter"
SPEC = VENDORED / "SwayNotificationCenter.spec"
MANIFEST = REPO / "build-order-hummingbird-desktops.yml"


@pytest.fixture(scope="module")
def spec_text():
    return SPEC.read_text()


def test_the_packaging_is_vendored_not_imported():
    """An imported spec is whatever Rawhide has today, which is the broken one."""
    assert SPEC.is_file(), f"{SPEC} is missing"
    assert (VENDORED / "sources").is_file(), "no sources file; the tarball cannot be fetched"


def test_the_manifest_builds_it_from_the_vendored_spec():
    order = yaml.safe_load(MANIFEST.read_text())
    entries = [p for tier in order["tiers"] for p in tier["packages"]
               if p["path"].endswith("/SwayNotificationCenter")]
    assert len(entries) == 1, f"expected exactly one entry, got {entries}"
    assert "distgit" not in entries[0], (
        "the manifest still imports SwayNotificationCenter from dist-git, which "
        "fetches 0.12.6 and its unsatisfiable granite-7 BuildRequires"
    )


def test_it_pins_the_version_fedora_actually_ships(spec_text):
    version = re.search(r"^Version:\s*(\S+)", spec_text, re.M).group(1)
    assert version == "0.10.1", (
        f"pinned to {version}; 0.12.6 needs granite-7 >= 7.5.0 and Rawhide has "
        "only Granite 6. If Granite 7 gets packaged, this pin can be lifted."
    )


def test_it_does_not_buildrequire_granite_7(spec_text):
    """The single capability nothing in Rawhide provides."""
    assert "granite-7" not in spec_text, (
        "the vendored spec still wants granite-7, which is the thing that "
        "could not be satisfied in the first place"
    )


def test_every_buildrequires_names_something(spec_text):
    """A typo here fails hours into a run, in a layer near the end."""
    brs = re.findall(r"^BuildRequires:\s*(\S+)", spec_text, re.M)
    assert len(brs) >= 15, f"only {len(brs)} BuildRequires; the spec looks truncated"
    for b in brs:
        assert not b.startswith("%"), f"unexpanded macro in BuildRequires: {b}"


def test_the_sources_entry_is_a_usable_sha512():
    """build-chain resolves the tarball through Fedora's lookaside cache using
    this line; a malformed one fails the download rather than the checksum."""
    text = (VENDORED / "sources").read_text().strip()
    match = re.match(r"^SHA512 \((.+)\) = ([0-9a-f]{128})$", text)
    assert match, f"sources is not a lookaside SHA512 entry: {text!r}"
    assert "0.10.1" in match.group(1), (
        f"sources names {match.group(1)}, which is not the pinned version"
    )
