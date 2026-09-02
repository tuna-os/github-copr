"""An autotools recipe must be able to influence its own link line (#469).

`build.environment` was wired into the cargo and go paths only. An autotools
recipe therefore had NO way to add a library to its link:

  - `configure_options` rejects anything not starting with "--", so
    `LIBS=-lgcc_s` could not go there;
  - nothing prefixed `%configure`, so `build.environment` was silently ignored.

That is not a style gap. libunwind needed `LIBS=-lgcc_s` on aarch64 and could
express it nowhere, so the published libunwind.so.8 shipped with four
UNDEFINED outline-atomics symbols and every consumer died at load:

    quickshell: symbol lookup error: /lib64/libunwind.so.8:
      undefined symbol: __aarch64_cas8_acq_rel

Verified against the published RPM: `readelf -d` showed libgcc_s.so.1 absent
from NEEDED while `__aarch64_cas8_acq_rel`, `__aarch64_swp1_acq_rel`,
`__aarch64_ldadd8_acq_rel` and `__aarch64_ldadd4_acq_rel` were all UND.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("tf", ROOT / "scripts" / "tideforge.py")
tf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tf)

RECIPE = ROOT / "packages" / "libunwind-devel" / "package.yaml"


def render(recipe):
    return tf.rpm_build_lines("autotools", recipe)[0]


def test_the_environment_reaches_the_autotools_build() -> None:
    build = render({"build": {"environment": {"LIBS": "-lgcc_s"}}})
    assert "export LIBS=-lgcc_s" in build


def test_it_is_exported_before_configure_runs() -> None:
    """A late export would not affect the configure tests that consume it."""
    build = render({"build": {"environment": {"LIBS": "-lgcc_s"}}})
    assert build.index("export LIBS") < build.index("%configure")


def test_it_is_exported_rather_than_prefixed() -> None:
    """`VAR=x %configure` applies to %configure's FIRST command only.

    %configure expands to a multi-line script, so a prefix assignment would
    silently cover part of it -- the shape most likely to look correct in a
    diff and fail in the buildroot.
    """
    build = render({"build": {"environment": {"LIBS": "-lgcc_s"}}})
    assert not any(
        line.strip().startswith("LIBS=") and "%configure" in line
        for line in build.splitlines()
    )
    assert any(line.startswith("export LIBS=") for line in build.splitlines())


def test_it_composes_with_autoreconf() -> None:
    build = render({"build": {"environment": {"LIBS": "-lgcc_s"}, "autoreconf": True}})
    lines = [l for l in build.splitlines() if l.strip()]
    assert lines[0].startswith("export LIBS=")
    assert lines[1] == "autoreconf -fi"
    assert lines[2].startswith("%configure")


def test_a_recipe_without_environment_is_unchanged() -> None:
    """Every already-working autotools recipe must render byte-identically.

    Pinned against what the renderer actually emitted before this change,
    trailing space after %configure included -- an assertion written from
    what the output "should" look like failed here and would have hidden a
    real regression behind a cosmetic one.
    """
    assert render({"build": {"autoreconf": True}}) == "autoreconf -fi\n%configure \n%make_build"
    assert render({}) == "%configure \n%make_build"
    assert "export" not in render({"build": {"autoreconf": True}})


def test_values_are_shell_quoted() -> None:
    build = render({"build": {"environment": {"LIBS": "-lgcc_s -lfoo bar"}}})
    assert "export LIBS='-lgcc_s -lfoo bar'" in build


# --- the recipe this exists for --------------------------------------------


def test_libunwind_links_libgcc() -> None:
    """Without this the aarch64 library has undefined outline-atomics symbols."""
    recipe = yaml.safe_load(RECIPE.read_text())
    assert recipe["build"]["environment"]["LIBS"] == "-lgcc_s"


def test_libunwind_does_not_clobber_the_hardened_ldflags() -> None:
    """LDFLAGS carries relro, -z now and the annobin specs from the distro
    macros; replacing it to add one library would silently drop all of them."""
    recipe = yaml.safe_load(RECIPE.read_text())
    assert "LDFLAGS" not in recipe["build"]["environment"]


def test_libunwind_renders_the_export() -> None:
    recipe = yaml.safe_load(RECIPE.read_text())
    assert "export LIBS=-lgcc_s" in render(recipe)
