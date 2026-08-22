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


def test_every_target_declares_a_wayland_protocols_provider():
    """src/wayland/CMakeLists.txt does an unconditional

        pkg_check_modules(... wayland-client;wayland-protocols>=1.41)

    so this is not optional on any target. It was missing on deb, which is
    where openSUSE had already failed one round earlier -- the same wall,
    found separately on each target because CMake stops at the first failing
    pkg_check_modules and each list was fixed in isolation.

    Stated over ALL targets rather than just the two that were fixed: that is
    the only form that would have caught deb from the openSUSE round.
    """
    providers = {
        "el10": "wayland-protocols",
        "ubuntu": "wayland-protocols",
        "debian": "wayland-protocols",
        "arch": "wayland-protocols",
        # openSUSE gets the virtual provide: the package search is
        # unreachable from CI, and pkgconfig() is name-independent anyway.
        "opensuse-tumbleweed": "pkgconfig(wayland-protocols)",
    }
    for target, provider in providers.items():
        assert provider in deps()[target], (target, provider)


def test_every_target_declares_a_gbm_provider():
    """el10 carries mesa-libgbm-devel and openSUSE pkgconfig(gbm), so
    quickshell genuinely needs a gbm provider -- deb simply had not reached
    that check yet, because CMake stops at wayland-protocols first.

    Arch is the exception on purpose: gbm ships inside `mesa` there, which is
    pulled in by the Qt/wayland stack, and there is no separate -dev package
    to name."""
    providers = {
        "el10": "mesa-libgbm-devel",
        "ubuntu": "libgbm-dev",
        "debian": "libgbm-dev",
        "opensuse-tumbleweed": "pkgconfig(gbm)",
    }
    for target, provider in providers.items():
        assert provider in deps()[target], (target, provider)


def test_the_deb_wayland_and_gbm_names_are_debian_spellings():
    """The EL and openSUSE spellings do not exist in the Debian archives; a
    name that does not resolve makes the cell fail EARLIER than the missing
    dependency it was meant to fix."""
    for target in ("ubuntu", "debian"):
        names = deps()[target]
        assert "mesa-libgbm-devel" not in names, target
        assert not [n for n in names if n.startswith("pkgconfig(")], target


def runtime_deps() -> dict:
    r = yaml.safe_load(RECIPE.read_text(encoding="utf-8"))
    return r["dependencies"]["runtime"]["targets"]


def test_arch_declares_its_runtime_closure():
    """makepkg does not populate depends=() -- it only warns -- so an
    undeclared shared library on Arch produces a package that installs
    cleanly and then cannot start:

        quickshell: error while loading shared libraries: libcpptrace.so.1

    rpmbuild auto-generates Requires from ELF sonames and dpkg-shlibdeps
    fills ${shlibs:Depends}, so no other target needs this -- which is why
    arch was the only one the smoke gate caught."""
    arch = runtime_deps()["arch"]
    assert "cpptrace" in arch, arch
    for lib in ("qt6-base", "qt6-declarative", "qt6-wayland", "pipewire", "libdrm"):
        assert lib in arch, (lib, arch)


def test_the_arch_runtime_names_are_all_known_good_on_arch():
    """Every runtime name must also appear in the arch BUILD list, which has
    already resolved against pacman. A runtime-only name would be unverified,
    and a wrong one turns a passing build into a failing install."""
    build = set(deps()["arch"])
    for name in runtime_deps()["arch"]:
        assert name in build, name


def test_header_only_and_disabled_libraries_are_not_runtime_deps():
    """cli11 is header-only, and jemalloc is not linked at all --
    build.cmake_options passes -DUSE_JEMALLOC=OFF. Listing either would make
    the installed package pull in something it never loads."""
    r = yaml.safe_load(RECIPE.read_text(encoding="utf-8"))
    assert "-DUSE_JEMALLOC=OFF" in r["build"]["cmake_options"]
    arch = runtime_deps()["arch"]
    assert "cli11" not in arch and "jemalloc" not in arch, arch


def test_only_arch_declares_runtime_deps():
    """The other targets derive their closure from the binary. Adding a hand
    list there would drift from what the linker actually needs."""
    assert set(runtime_deps()) == {"arch"}, sorted(runtime_deps())
