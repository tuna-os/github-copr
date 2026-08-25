"""A %install that goes to PyPI, and why --no-deps did not stop it.

input-remapper does not install with pip -- the spec says so at length, and
means it: upstream's own installer is what places the udev rules, polkit
action, systemd unit and D-Bus policy. But that installer shells out to pip
for the Python module:

    pip install . --target <buildroot>/.../site-packages --no-deps

`--no-deps` suppresses RUNTIME dependency resolution. It says nothing about
PEP 517 BUILD dependencies, and by default pip builds the sdist in an
ISOLATED environment that it populates FROM PYPI -- so it reaches the network
before it looks at anything local. mock has no network in %install:

    ERROR: Could not find a version that satisfies the requirement
           setuptools>=40.8.0 (from versions: none)
    ERROR: No matching distribution found for setuptools>=40.8.0
    error: Bad exit status from /var/tmp/rpm-tmp.eJf98H (%install)

gnome50-el10, both arches, run 32674169357 -- the only failed package in that
chain, and the one left standing after the changelog-macro fix landed.

PIP_NO_BUILD_ISOLATION points pip at the buildroot's setuptools, which is
what BuildRequires is for. PIP_NO_INDEX is the second half and the more
useful one long-term: with no index, anything still reaching for the network
fails at once and NAMES what it wanted, instead of five connection retries
and a message about the connection. A buildroot that needs the network has an
undeclared BuildRequires, and this is what makes it say so.

These assert against the PARSED %install section, not the file text. A spec
mentioning PIP_NO_INDEX in a comment or a changelog entry must not satisfy
them -- the whole failure being fixed is a directive that was present as prose
and absent as behaviour.
"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "src" / "input-remapper" / "input-remapper.spec"

SECTIONS = (
    "%prep", "%build", "%install", "%check", "%files",
    "%changelog", "%package", "%description", "%post", "%postun",
    "%pre", "%preun",
)


def section(name: str) -> str:
    """The body of one spec section, comments and directives stripped."""
    out, inside = [], False
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        head = line.split()[0] if line.split() else ""
        if head in SECTIONS:
            inside = head == name
            continue
        if inside and not line.lstrip().startswith("#"):
            out.append(line)
    return "\n".join(out)


def build_requires() -> set[str]:
    return {
        ln.split(":", 1)[1].strip()
        for ln in SPEC.read_text(encoding="utf-8").splitlines()
        if ln.startswith("BuildRequires:")
    }


def test_the_section_parser_finds_the_install_body():
    """Every assertion below is vacuous if this returns nothing."""
    body = section("%install")
    assert body.strip(), "no %install body parsed"
    assert "python3 -m install" in body, body


@pytest.mark.parametrize(
    "var", ["PIP_NO_BUILD_ISOLATION", "PIP_NO_INDEX"]
)
def test_pip_is_kept_off_the_network_in_install(var):
    body = section("%install")
    assert f"export {var}=1" in body, (
        f"{var} is not exported in the %install body; a mention in a comment "
        "or changelog does not reach pip"
    )


def test_the_backend_pip_is_told_to_reuse_is_actually_installed():
    """Turning isolation off without providing the backend just moves the error."""
    br = build_requires()
    assert "python3-setuptools" in br, br
    assert "python3-wheel" in br, br


def test_the_changelog_records_the_release_that_carries_this():
    text = SPEC.read_text(encoding="utf-8")
    assert "Release:        3%{?dist}" in text
    assert "2.2.1-3" in text, "the changelog does not name the new release"


def test_no_spec_in_the_tree_disables_network_by_patching_upstream():
    """The fix must be environment, not a patch to someone else's installer.

    Patching install/module.py would work once and rot at every rebase; the
    PIP_* variables reach the same pip without owning their code.
    """
    body = section("%install")
    assert "sed -i" not in body, body
    assert ".patch" not in body, body
