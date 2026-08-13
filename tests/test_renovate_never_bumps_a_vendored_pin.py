"""A one-line digest bump must not be possible where the pin is not one line.

Some sources carry a pre-vendored dependency tree, published as a release
asset whose name embeds the commit it was vendored from, plus a cargo source
override repeating a git rev that the upstream commit's Cargo.lock chose.
Bumping the commit without regenerating both leaves `cargo build --offline`
unable to resolve the dependency at all.

That is not hypothetical. renovate bumped src/xfce-wayland/xfwl4/xfwl4.spec's
`%global commit` -- and nothing else -- four times:

    9ed4f7c (#376)  179316f5   vendor 5c2802c0   smithay 0a29aecf
    a6e8b62 (#368)  718c7c19   vendor 5c2802c0   smithay 0a29aecf
    fddc3b9 (#366)  c6c0e1ca   vendor 5c2802c0   smithay 0a29aecf
    7e6fe4d (#361)  cbcc18be   vendor 5c2802c0   smithay 0a29aecf   <- last green

It worked while upstream still pinned smithay at 0a29aecf and stopped the
moment upstream moved to 4cf0b620, at #366. XFCE Wayland (Fedora) was red on
main from 2026-08-12 onward while three more one-line bumps landed on top,
each looking like an ordinary dependency chore.

renovate.json already carried this exact reasoning as the justification for
keeping packages/xfwl4/package.yaml out of the manager. The spec and the
PKGBUILD have the same coupling and were left in.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RENOVATE = ROOT / "renovate.json"

# A release asset whose name embeds the commit it was vendored from.
VENDORED_ASSET = re.compile(r"releases/download/[A-Za-z0-9._-]+-vendor-[0-9a-f]{6,40}/")

SEARCH_ROOTS = ("src", "packages")
SEARCH_SUFFIXES = (".spec", ".yaml", ".yml", "PKGBUILD")


def _managers():
    return json.loads(RENOVATE.read_text()).get("customManagers", [])


def _files_with_a_vendored_pin():
    found = []
    for root in SEARCH_ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if not path.name.endswith(SEARCH_SUFFIXES):
                continue
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            if VENDORED_ASSET.search(text):
                found.append(path.relative_to(ROOT))
    return sorted(found)


def test_the_repo_still_has_a_vendored_pin_to_guard():
    """Otherwise every assertion below is vacuously true."""
    assert _files_with_a_vendored_pin(), (
        "no commit-keyed vendor asset found under "
        f"{SEARCH_ROOTS}; this guard is no longer testing anything"
    )


def test_renovate_json_is_valid():
    json.loads(RENOVATE.read_text())


@pytest.mark.parametrize("path", _files_with_a_vendored_pin(), ids=str)
def test_no_regex_manager_matches_a_file_with_a_vendored_pin(path):
    posix = path.as_posix()
    for manager in _managers():
        for pattern in manager.get("fileMatch", []):
            assert not re.search(pattern, posix), (
                f"renovate manager {manager.get('depNameTemplate')!r} matches "
                f"{posix}, which pins a vendored dependency tree by commit. A "
                "regex manager can only rewrite the digest, so it will ship a "
                "commit whose vendor asset and cargo source override still "
                "point at the old one, and the offline build cannot resolve "
                "the dependency. Bump this by hand, regenerating the vendor "
                "asset and the rev, or leave the manager disabled."
            )


def test_the_disabled_xfwl4_manager_says_why():
    xfwl4 = [m for m in _managers() if m.get("depNameTemplate") == "xfwl4"]
    if not xfwl4:
        pytest.skip("the xfwl4 manager was removed outright rather than disabled")
    description = xfwl4[0].get("description", "")
    assert "vendor" in description and "smithay" in description, (
        "a disabled manager with no stated reason gets re-enabled by the next "
        f"person who notices xfwl4 is not being updated: {description!r}"
    )


def test_the_spec_and_the_pkgbuild_pin_the_same_commit():
    """They are two packagings of one source; a split is a silent skew."""
    spec = (ROOT / "src/xfce-wayland/xfwl4/xfwl4.spec").read_text()
    pkgbuild = (ROOT / "src/xfce-wayland/xfwl4/packaging/arch/PKGBUILD").read_text()

    spec_commit = re.search(r"^%global commit ([0-9a-f]{40})", spec, re.M)
    pkg_commit = re.search(r"^_commit=([0-9a-f]{40})", pkgbuild, re.M)
    assert spec_commit and pkg_commit, "could not read both pinned commits"
    assert spec_commit.group(1) == pkg_commit.group(1), (
        f"spec pins {spec_commit.group(1)} but the Arch PKGBUILD pins "
        f"{pkg_commit.group(1)}"
    )
