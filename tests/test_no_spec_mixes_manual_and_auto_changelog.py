"""A spec may have a hand-written %changelog or %autochangelog, never both.

rpmautospec generates changelog entries from git commit dates. A hand-written
entry sitting ABOVE %autochangelog is therefore older than the entries rpm
sees generated below it, and rpm rejects the section:

    error: %changelog not in descending chronological order

That killed gnome-desktop3 in leg 33045828544 and, once the gnome-51 specs
were fixed, gdm/gnome-shell/gnome-session would each have died the same way
when the chain reached them -- 25 specs across gnome-50, gnome-51 and deps
carried the pattern, every one a build that had to fail first to be found.

The fix is always the same: delete the manual entries. They are not lost --
%autochangelog reads them from git, which is the whole point of it.

This test is the cheap version of that discovery: a second of static
analysis instead of a tier-deep chain failure hours in.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPECS = sorted(ROOT.glob("src/**/*.spec"))


def changelog_body(spec: Path) -> str | None:
    text = spec.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^%changelog\b", text, re.M)
    if not match:
        return None
    return text[match.end():]


@pytest.mark.parametrize("spec", SPECS, ids=lambda p: str(p.relative_to(ROOT)))
def test_manual_entries_never_sit_above_autochangelog(spec):
    body = changelog_body(spec)
    if body is None or "%autochangelog" not in body:
        return
    above = body.split("%autochangelog", 1)[0]
    entries = [ln for ln in above.splitlines() if ln.startswith("*")]
    assert not entries, (
        f"{spec.relative_to(ROOT)}: {len(entries)} hand-written changelog "
        f"entr{'y' if len(entries) == 1 else 'ies'} above %autochangelog "
        f"(first: {entries[0][:60]!r}). rpmautospec's git-derived entries are "
        "newer, so rpm sees ascending order and fails the build. Delete them; "
        "git still has them, and %autochangelog is what reads git."
    )


def test_the_scan_actually_covers_the_tree():
    assert len(SPECS) > 50, (
        f"only {len(SPECS)} specs found -- a glob that stops matching turns "
        "this guard into a no-op that passes forever"
    )
