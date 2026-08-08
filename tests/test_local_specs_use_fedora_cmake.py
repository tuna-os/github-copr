"""Locally-maintained specs must use Fedora's cmake macros, not EL's.

`cmake3` and `%cmake3*` come from EPEL, where cmake 2 was still the default
and cmake 3 needed a separate name. On Fedora the package is `cmake` and the
macros are `%cmake`, `%cmake_build`, `%cmake_install`. There is no `cmake3` in
any repo the Hummingbird buildroot has, so a spec asking for it dies before
rpmbuild starts:

    Failed to resolve the transaction:
    No match for argument: cmake3

which is what happened to src/deps/libldac in gnome-00 of run 31274954342 --
the last failure in that tier that was not either a legacy-md5 sources file
(#286) or a %find_lang problem.

The distinction is easy to miss because the spec builds fine on EL and the
error names the argument rather than the spec. Specs imported from dist-git
are Fedora's own and are not checked here; this is about the ones this
repository maintains.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LOCAL_SPEC_DIRS = ["src/deps", "src/hummingbird", "src/gnome-50", "src/xfce-wayland"]

EL_ONLY = re.compile(r"(?:^BuildRequires:\s*cmake3\b|^%cmake3(?:_build|_install)?\b)", re.M)


def local_specs():
    for prefix in LOCAL_SPEC_DIRS:
        root = REPO / prefix
        if root.is_dir():
            yield from sorted(root.glob("*/*.spec"))


def test_there_are_local_specs_to_check():
    assert list(local_specs()), "no local specs found; the glob is wrong"


@pytest.mark.parametrize("spec", list(local_specs()), ids=lambda p: p.parent.name)
def test_spec_does_not_use_el_cmake3(spec):
    offenders = EL_ONLY.findall(spec.read_text())
    assert not offenders, (
        f"{spec.relative_to(REPO)} uses EL's cmake3 ({offenders}); the "
        "Hummingbird buildroot has no cmake3 and dnf fails with "
        "'No match for argument: cmake3'. Use cmake / %cmake / %cmake_build / "
        "%cmake_install."
    )
