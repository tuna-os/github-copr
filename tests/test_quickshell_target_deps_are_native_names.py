"""Each quickshell target must name packages the way ITS distro names them.

Seven of quickshell's nine cells had never been green, and each family failed
for a different reason. All three were measured in run 32541649752, not
inferred from the shape of the lists:

  arch  `pacman` answered `target not found: cli11-devel`, `cpptrace-devel`
        and `ninja-build`. Those are EL spellings. Arch ships all three in
        `extra` as cli11, cpptrace and ninja.

  suse  build-deps resolved fine; CMake then failed with
        `Failed to find required Qt component "QuickPrivate"`. QuickPrivate
        ships in the DECLARATIVE private package, not the base private one
        the list already carried.

  deb   Debian sid installed libcli11-dev (2.6.1+ds-1) and libcpptrace-dev
        (1.0.4-2) from its own archive without complaint; the only gap was
        ninja-build, because build.cmake_generator is Ninja.

The deb names are deliberately NOT changed to the factory's own
`cpptrace-devel`: the cpptrace-devel recipe declares an `outputs.deb.packages`
entry named `libcpptrace-dev`, so the Debian spelling is what the factory
itself publishes as well as what Debian ships.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "packages" / "quickshell" / "package.yaml"


def deps() -> dict:
    r = yaml.safe_load(RECIPE.read_text(encoding="utf-8"))
    return r["dependencies"]["build"]["targets"]


def test_arch_uses_arch_package_names():
    arch = deps()["arch"]
    assert "cli11" in arch and "cpptrace" in arch and "ninja" in arch


def test_arch_has_the_vulkan_headers_el10_gets_transitively():
    """Round 2: with the names fixed, arch reached CMake and then failed on
    find_package(VulkanHeaders). el10 lists no vulkan package and passes, so
    it arrives transitively there and not on Arch."""
    assert "vulkan-headers" in deps()["arch"]


def test_opensuse_asks_for_capabilities_not_guessed_package_names():
    """This environment cannot reach the openSUSE package search (401/403), so
    a literal name would be a guess. Every RPM distro exposes pkgconfig(foo)
    as a virtual provide, so the capability resolves without knowing what
    openSUSE calls the package."""
    suse = deps()["opensuse-tumbleweed"]
    assert "pkgconfig(wayland-protocols)" in suse
    assert "pkgconfig(gbm)" in suse


def test_the_capabilities_render_as_rpm_buildrequires():
    """A capability that the renderer mangles would fail at spec-parse time
    rather than resolving."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import tideforge

    recipe = yaml.safe_load(RECIPE.read_text(encoding="utf-8"))
    rendered = tideforge.target_dependencies(recipe, "opensuse-tumbleweed")
    assert "pkgconfig(wayland-protocols)" in rendered


def test_arch_carries_no_el_or_deb_spellings():
    """The exact three names pacman rejected, plus any other -devel leak."""
    arch = deps()["arch"]
    for rejected in ("cli11-devel", "cpptrace-devel", "ninja-build"):
        assert rejected not in arch, rejected
    assert not [p for p in arch if p.endswith("-devel") or p.endswith("-dev")], arch


def test_opensuse_has_the_declarative_private_headers():
    """QuickPrivate is in declarative, not base -- the base private package
    was already present and did not satisfy find_package."""
    suse = deps()["opensuse-tumbleweed"]
    assert "qt6-declarative-private-devel" in suse


def test_deb_targets_have_a_ninja_since_the_generator_is_ninja():
    r = yaml.safe_load(RECIPE.read_text(encoding="utf-8"))
    assert r["build"]["cmake_generator"] == "Ninja"
    for target in ("ubuntu", "debian"):
        assert "ninja-build" in deps()[target], target


def test_deb_targets_keep_the_debian_spellings():
    """cpptrace-devel's own recipe publishes a deb named libcpptrace-dev, and
    Debian ships one too. Renaming these to the EL spelling would break both
    sources at once."""
    for target in ("ubuntu", "debian"):
        names = deps()[target]
        assert "libcpptrace-dev" in names and "libcli11-dev" in names, target
        assert "cpptrace-devel" not in names and "cli11-devel" not in names, target


def test_every_target_in_the_recipe_has_a_dependency_list():
    r = yaml.safe_load(RECIPE.read_text(encoding="utf-8"))
    assert set(r["targets"]) == set(deps()), (r["targets"], sorted(deps()))
