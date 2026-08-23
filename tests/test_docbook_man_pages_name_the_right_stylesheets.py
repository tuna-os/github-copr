"""The DocBook stylesheet a spec BuildRequires has to be the one upstream probes.

libnotify failed configure in gnome51-el10-aarch64 (run 32604266038) with:

    meson.build:78:4: ERROR: Problem encountered: DocBook stylesheet for
    generating man pages not found, you need to install docbook-xsl-ns or
    similar package.

The spec BuildRequired `docbook-style-xsl`, which is present on EL10 and is
the wrong set. libnotify's meson.build probes the NAMESPACED stylesheet, and
it does so offline:

    run_command(xsltproc, '--nonet',
      'http://docbook.sourceforge.net/release/xsl-ns/current/manpages/docbook.xsl')

`--nonet` means that URI must resolve through /etc/xml/catalog, so the
buildroot needs a package whose %post registers a rewrite rule for it.
Measured against CentOS Stream 10 BaseOS/AppStream/CRB, aarch64:

    docbook-style-xsl     xsl-stylesheets-1.79.2      present, no xsl-ns rule
    docbook5-style-xsl    xsl-ns-stylesheets-1.79.2   present, and its %post runs
                            xmlcatalog --add rewriteURI
                            "http://docbook.sourceforge.net/release/xsl-ns/current"
    docbook-style-xsl-ns  (the Fedora name)           ABSENT
    docbook-xsl-ns        (the Debian name the error suggests)  ABSENT
    docbook-xsl           (the plain Debian name)     ABSENT

So on EL10 the namespaced set exists only under the name `docbook5-style-xsl`,
and the error message's own suggestion names a package that cannot be
installed. Both wrong answers -- keeping docbook-style-xsl, or believing the
error message -- cost a full cell run to discover, and a gnome cell is ~2.5h.

The rule here is deliberately narrow. It does NOT say "every spec generating
man pages needs the namespaced set": most of this factory's specs
(gtk4, gnome-control-center, thunar, xfce4-terminal) probe the
non-namespaced `xsl/current` URI and are correct with `docbook-style-xsl`.
Which package is right depends on which URI the upstream meson.build asks
for, and that is not visible in the spec. A rule broad enough to decide it
from the spec alone would flag the correct ones too.

What is checkable without guessing is narrower and still catches the class:
no spec may BuildRequire a docbook stylesheet package that EL10 does not
ship at all, and the two specs known to need the namespaced set must keep
naming it.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Names that do not exist in any repository the el10 buildroot can reach.
# Measured, not assumed -- see the module docstring.
ABSENT_ON_EL10 = ("docbook-style-xsl-ns", "docbook-xsl-ns", "docbook-xsl")

# The one EL10 name for the namespaced (xsl-ns) stylesheets.
NAMESPACED = "docbook5-style-xsl"

BUILDREQUIRES = re.compile(r"^BuildRequires:\s*(.+)$", re.MULTILINE | re.IGNORECASE)


def specs() -> list[Path]:
    return sorted(ROOT.rglob("*.spec"))


def build_requires(spec: Path) -> list[str]:
    """Every name on every BuildRequires line, one line often listing several."""
    text = spec.read_text(encoding="utf-8", errors="replace")
    names: list[str] = []
    for line in BUILDREQUIRES.findall(text):
        # Drop version constraints: `foo >= 1.2` contributes `foo`.
        parts = re.split(r"\s+", line.strip())
        skip = False
        for part in parts:
            if part in (">=", "<=", "=", ">", "<"):
                skip = True
                continue
            if skip:
                skip = False
                continue
            names.append(part)
    return names


def absent_requirements(spec: Path) -> list[str]:
    """BuildRequires naming a docbook package EL10 does not have.

    Exact match: `docbook-xsl` must not swallow `docbook-xsl-stylesheets` or,
    more to the point, must not match `docbook-style-xsl` -- which does exist.
    """
    return sorted({name for name in build_requires(spec) if name in ABSENT_ON_EL10})


def test_there_are_specs_to_check():
    """A sweep over an empty set passes for the wrong reason."""
    assert len(specs()) > 50


def test_no_spec_requires_a_docbook_package_el10_does_not_have():
    offenders = {
        str(spec.relative_to(ROOT)): found
        for spec in specs()
        if (found := absent_requirements(spec))
    }
    assert not offenders, offenders


def test_libnotify_requires_the_namespaced_stylesheets():
    """The spec that broke, pinned by content so it survives edits above it."""
    spec = ROOT / "src" / "deps" / "libnotify" / "libnotify.spec"
    names = build_requires(spec)
    assert NAMESPACED in names, names
    assert "docbook-style-xsl" not in names, (
        "the non-namespaced set does not register the xsl-ns catalog rewrite "
        "meson.build:78 probes for"
    )
    # The BuildRequires only matters because man pages are enabled. If the
    # option ever goes away the requirement is dead weight, and if it is
    # silently dropped the man page EL10's own libnotify ships disappears.
    text = spec.read_text(encoding="utf-8")
    assert "-Dman=true" in text
    assert "%{_mandir}/man1/notify-send.1*" in text


def test_colord_gtk_shows_the_same_choice():
    """Not a second pin so much as evidence the name is right: colord-gtk
    already builds on EL10 asking for the namespaced set."""
    spec = ROOT / "src" / "gnome-49" / "colord-gtk" / "colord-gtk.spec"
    assert NAMESPACED in build_requires(spec)


def test_specs_probing_the_plain_stylesheets_are_not_flagged():
    """docbook-style-xsl is a correct answer for the projects that ask for the
    non-namespaced URI. Flagging them would be noise."""
    for rel in (
        ("src", "gnome-51", "gnome-control-center", "gnome-control-center.spec"),
        ("src", "xfce-wayland", "thunar", "thunar.spec"),
    ):
        spec = ROOT.joinpath(*rel)
        assert "docbook-style-xsl" in build_requires(spec)
        assert absent_requirements(spec) == []


def test_the_rule_would_catch_believing_the_error_message(tmp_path):
    """Mutation in miniature: taking the error message's suggestion literally
    names a package EL10 does not have, and must be flagged."""
    broken = tmp_path / "broken.spec"
    broken.write_text(
        "Name: libnotify\n"
        "BuildRequires:  libxslt\n"
        "BuildRequires:  docbook-xsl-ns\n"
        "\n"
        "%prep\n",
        encoding="utf-8",
    )
    assert absent_requirements(broken) == ["docbook-xsl-ns"]


def test_a_versioned_requirement_still_parses_to_its_name(tmp_path):
    spec = tmp_path / "versioned.spec"
    spec.write_text(
        "Name: x\nBuildRequires:  docbook5-style-xsl >= 1.79.2\n%prep\n",
        encoding="utf-8",
    )
    assert "docbook5-style-xsl" in build_requires(spec)
    assert absent_requirements(spec) == []
