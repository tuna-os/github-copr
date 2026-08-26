"""RPM expands macros in %changelog text, and one of them is not inert.

gnome50-el10-aarch64 built 57 packages across 19 tiers of run 32646102181 and
then died on the 58th:

    error: line 114: %package debuginfo
    : package input-remapper-debuginfo already exists

Line 114 of input-remapper.spec is not a spec directive. It is changelog prose
added two days earlier:

      installer shells out to pip and imports gi, so %install failed in mock

`%install` is a macro rpm DEFINES, not merely a section keyword, so it expands
where it appears and re-emits the install scaffolding -- including the
automatic debuginfo subpackage, which by then already exists. The error is
reported at the changelog line, which is the only reason it was findable.

The discriminating evidence, and the reason this test forbids the whole class
rather than that one word: `src/gnome-50/mutter` and `src/gnome-50/gjs` are in
the SAME build order, were built in the SAME run, and carry `%prep`, `%build`
and `%files` in their changelogs. They passed. Those are section keywords with
no macro definition behind them; `%install` has one.

So the precise rule is "escape any macro rpm happens to define", and the set
rpm defines is not ours to track -- it changes with an rpm release, and this
particular line sat harmless in the tree for two days before it fired. The
cheap rule that subsumes it is the one Fedora packaging already states: escape
the percent sign in changelog text. That is what this enforces.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Section keywords and the rpm-defined macros that shadow them. `install` is
# the one with measured consequences; the rest are here because deciding which
# of them rpm defines TODAY is exactly the reasoning that let this through.
RISKY = {
    "install", "build", "prep", "check", "files", "package", "description",
    "post", "postun", "pre", "preun", "posttrans", "pretrans", "clean",
    "configure", "make_build", "make_install", "autosetup", "setup",
}

PATTERN = re.compile(r"(?<!%)%([A-Za-z_]\w*)")


def unescaped_macros_in_changelogs() -> list[str]:
    findings = []
    for spec in sorted(ROOT.joinpath("src").rglob("*.spec")):
        in_changelog = False
        for number, line in enumerate(
            spec.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if line.startswith("%changelog"):
                in_changelog = True
                continue
            if not in_changelog:
                continue
            for match in PATTERN.finditer(line):
                if match.group(1) in RISKY:
                    findings.append(
                        f"{spec.relative_to(ROOT)}:{number}: {match.group(0)} "
                        f"-> write %%{match.group(1)}  | {line.strip()[:60]}"
                    )
    return findings


def test_no_spec_changelog_contains_an_unescaped_macro():
    findings = unescaped_macros_in_changelogs()
    assert not findings, (
        "changelog prose is macro-expanded by rpm; double the percent sign:\n"
        + "\n".join(findings)
    )


def test_the_line_that_broke_input_remapper_is_fixed():
    """Named explicitly, so a revert cannot pass by deleting the sweep above."""
    spec = ROOT / "src" / "input-remapper" / "input-remapper.spec"
    text = spec.read_text(encoding="utf-8")
    changelog = text[text.index("%changelog"):]
    assert "%%install failed in mock" in changelog
    assert "so %install failed" not in changelog
