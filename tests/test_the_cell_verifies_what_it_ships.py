"""The verify step must install what the chain ships, and only that.

gnome51-el10-aarch64 at 8086e03 reported "All packages built successfully!"
with 55 packages and a clean lint, then failed in the verify step -- the next
layer down, and one no gnome cell had reached before. Two independent defects:

1. DUPLICATE NEVRAs. The step ran `dnf install /factory-repo/*.rpm`, passing
   every built FILE. A build-chain tier list may build the same recipe twice
   on purpose:

       tier 2 glib2-bootstrap  src/gnome-51/glib2
       tier 6 glib2-full       src/gnome-51/glib2
       tier 5 gi-bootstrap     src/gnome-51/gobject-introspection
       tier 7 gi-full          src/gnome-51/gobject-introspection

   so /artifacts holds two EVRs of each, and asking dnf for both at once is
   unsatisfiable by construction:

       cannot install both glib2-2.88.0-4.el10.aarch64 from @commandline
       and glib2-2.88.0-1.el10.aarch64 from @commandline

   Installing by NAME resolves each to the newest EVR in the factory repo --
   the build the chain means to ship -- while rpm -q and rpm -V still cover
   every name, so coverage is unchanged. This is why only gnome cells hit it:
   xfce and fprintd have no bootstrap pass, which is also why the step looked
   correct for as long as it did.

2. tigervnc. avahi-ui-tools carried a hard `Requires: tigervnc`, and EL10 has
   no tigervnc in BaseOS, AppStream, CRB or EPEL, on either arch -- measured
   against the repository metadata, where EPEL 10 lists 25573 names and none
   of them is tigervnc. So the subpackage could not be installed on this
   target at all:

       nothing provides tigervnc needed by avahi-ui-tools-0.9~rc2-8.el10.aarch64

   Recommends is the fix rather than deletion: the package installs where
   tigervnc is absent and still pulls it in where it exists. Only bvnc needs
   it; bssh and the rest of the subpackage do not.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify-package-factory-cell.sh"


def test_the_build_chain_verify_installs_by_name_not_by_file():
    text = VERIFY.read_text(encoding="utf-8")
    # The install must name the resolved package list...
    assert '"${names[@]}"\n' in text
    # ...and must not hand dnf a glob of every built file.
    assert "/factory-repo/*.rpm\n" not in text, (
        "installing every file re-introduces the duplicate-NEVRA failure"
    )
    # names must be computed before it is used to install.
    computed = text.index("mapfile -t names")
    installed = text.index("dnf -y install --nogpgcheck --repofrompath factory")
    assert computed < installed, "names is used before it is set"


def test_every_name_is_still_queried_and_verified():
    """Installing by name must not quietly shrink what gets checked."""
    text = VERIFY.read_text(encoding="utf-8")
    assert 'rpm -q "${names[@]}"' in text
    assert 'rpm -V "${names[@]}"' in text


def test_a_recipe_really_is_built_twice_in_the_gnome_chains():
    """The premise of the fix, asserted rather than assumed. If the bootstrap
    passes ever go away this test should be removed, not worked around."""
    for order in ("build-order.yml", "build-order-gnome51.yml"):
        data = yaml.safe_load((ROOT / order).read_text(encoding="utf-8"))
        paths = [
            pkg["path"]
            for tier in data.get("tiers", [])
            for pkg in (tier.get("packages") or [])
            if pkg.get("path")
        ]
        repeated = {path for path, n in Counter(paths).items() if n > 1}
        assert repeated, f"{order}: expected at least one recipe built twice"
        assert any("glib2" in p for p in repeated), (order, repeated)


def test_avahi_does_not_hard_require_something_el10_lacks():
    text = (ROOT / "src" / "deps" / "avahi" / "avahi.spec").read_text(encoding="utf-8")
    assert re.search(r"^Recommends:\s+tigervnc\s*$", text, re.M), text[:0]
    assert not re.search(r"^Requires:\s+tigervnc\s*$", text, re.M), (
        "a hard Requires on tigervnc makes avahi-ui-tools uninstallable on EL10"
    )
