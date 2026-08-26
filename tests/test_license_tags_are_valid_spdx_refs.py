"""A License tag must carry SPDX identifiers rpmlint will accept.

gnome51-el10-x86_64 built cleanly at 39b5632 -- 55 packages, zero failed --
and then failed anyway, in a step no gnome cell had ever reached before:

    lint-generated-rpm: FATAL finding 'invalid-license' in generated RPM
    libglib-testing.x86_64:  W: invalid-license LicenseRef-Callaway-LGPLv2+
    tinysparql-doc.noarch:   W: invalid-license LicenceRef-Fedora-Public-Domain

Two different defects, both in metadata rather than in any build:

  LicenseRef-Callaway-LGPLv2+   SPDX permits only [A-Za-z0-9.-] in a
                                LicenseRef idstring, so the trailing `+`
                                makes the whole token invalid. The same
                                spec's neighbours are fine precisely because
                                they have no `+`: plasma-workspace carries
                                LicenseRef-Callaway-GFDL and passes.
                                Fedora's legacy Callaway "LGPLv2+" is SPDX
                                LGPL-2.1-or-later, which needs no LicenseRef.

  LicenceRef-Fedora-Public-Domain   "Licence" with a c. Not a LicenseRef at
                                all, just a misspelling. Six other specs in
                                this repository spell the same license
                                correctly and lint clean, which is what
                                proves the intended spelling.

Only the -doc subpackage of tinysparql was flagged, which looks odd until you
notice line 103 is that subpackage's own License tag rather than the main
package's -- the main package is plain GPL-2.0-or-later.

Scope note: `invalid-license` is one of six findings scripts/lint-generated-rpm.sh
treats as fatal out of the thousands rpmlint reports (341 packages, 3797
findings, 6280 filtered on that run). This file checks the tag, not rpmlint's
whole opinion.

Changelog prose is deliberately excluded: the entries that record these two
fixes quote the broken tokens, and rpmlint reads the License tag, not the
changelog.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LICENSE_TAG = re.compile(r"^License:\s*(.+?)\s*$", re.MULTILINE)
# Any token that is trying to be a LicenseRef, however it is spelled.
REFISH = re.compile(r"\b(Licen[cs]eRef)-(\S+)")
# What SPDX actually allows after "LicenseRef-".
VALID_IDSTRING = re.compile(r"^[A-Za-z0-9.-]+$")


def specs() -> list[Path]:
    return sorted(ROOT.rglob("*.spec"))


def bad_license_refs(spec: Path) -> list[str]:
    """Offending tokens on License: lines only."""
    found = []
    for value in LICENSE_TAG.findall(spec.read_text(encoding="utf-8", errors="replace")):
        for keyword, idstring in REFISH.findall(value):
            if keyword != "LicenseRef":
                found.append(f"{keyword}-{idstring} (misspelled)")
            elif not VALID_IDSTRING.match(idstring):
                found.append(f"{keyword}-{idstring} (idstring not [A-Za-z0-9.-])")
    return found


def test_there_are_specs_to_check():
    assert len(specs()) > 50


def test_no_spec_carries_an_invalid_license_ref():
    offenders = {
        str(spec.relative_to(ROOT)): found
        for spec in specs()
        if (found := bad_license_refs(spec))
    }
    assert not offenders, offenders


def test_the_two_specs_that_failed_are_fixed():
    """Pinned by content, so they survive edits above them."""
    glib_testing = (ROOT / "src/deps/libglib-testing/libglib-testing.spec").read_text(
        encoding="utf-8"
    )
    assert "License:        LGPL-2.1-or-later" in glib_testing
    assert "License:        LicenseRef-Callaway-LGPLv2+" not in glib_testing

    for rel in ("src/deps/tinysparql/tinysparql.spec",
                "src/gnome-49/tinysparql/tinysparql.spec"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "License:        LicenseRef-Fedora-Public-Domain AND" in text, rel


def test_a_valid_licenseref_is_not_flagged(tmp_path):
    """LicenseRef-Callaway-GFDL and LicenseRef-Fedora-Public-Domain are both
    legal. A rule that flagged every LicenseRef would be noise."""
    ok = tmp_path / "ok.spec"
    ok.write_text(
        "Name: x\n"
        "License:        HPND AND LicenseRef-Fedora-Public-Domain AND Unicode-DFS-2016\n"
        "%package doc\n"
        "License:        LicenseRef-Callaway-GFDL\n"
        "%prep\n",
        encoding="utf-8",
    )
    assert bad_license_refs(ok) == []


def test_the_rule_would_catch_both_original_defects(tmp_path):
    broken = tmp_path / "broken.spec"
    broken.write_text(
        "Name: x\n"
        "License:        LicenseRef-Callaway-LGPLv2+\n"
        "%package doc\n"
        "License:        LicenceRef-Fedora-Public-Domain AND LGPL-2.1-or-later\n"
        "%prep\n",
        encoding="utf-8",
    )
    assert bad_license_refs(broken) == [
        "LicenseRef-Callaway-LGPLv2+ (idstring not [A-Za-z0-9.-])",
        "LicenceRef-Fedora-Public-Domain (misspelled)",
    ]


def test_changelog_prose_is_not_mistaken_for_a_tag(tmp_path):
    """The real fixes quote the broken tokens in their changelog entries."""
    spec = tmp_path / "changelog.spec"
    spec.write_text(
        "Name: x\n"
        "License:        LGPL-2.1-or-later\n"
        "%changelog\n"
        "* Sun Aug 23 2026 Someone <a@b.c> - 1-1\n"
        "- LicenseRef-Callaway-LGPLv2+ is not a valid LicenseRef\n",
        encoding="utf-8",
    )
    assert bad_license_refs(spec) == []
