"""gdm must not unconditionally Requires: a package that only exists on el10.

gnome50-el10-compat is only produced by build-order-gnome51.yml's src/deps/;
it does not exist anywhere in build-order-hummingbird-desktops.yml (the
Fedora-Rawhide-based target this spec also builds under). An unconditional
`Requires: gnome50-el10-compat` is therefore a hard, unsatisfiable dependency
on hummingbird -- rpmbuild itself never checks Requires: satisfiability, so
gdm builds clean regardless, but it broke `dnf5 builddep` for every OTHER
package that needs gdm-devel, gnome-initial-setup among them:

    nothing provides gnome50-el10-compat needed by gdm-51~beta-1.fc43.x86_64

Confirmed by an actual build, iterating the GNOME 51 chain locally: gdm
itself built fine; gnome-initial-setup's builddep step failed on this line
alone. Guarding it behind %if 0%{?rhel} (gdm.spec's own existing convention,
already used at the top of the file for %bcond x11) fixed it, verified by a
forced rebuild (NVR unchanged) whose resulting RPM's own --requires no
longer lists gnome50-el10-compat at all.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "src/gnome-51/gdm/gdm.spec"


def test_the_el10_compat_requires_is_guarded_by_rhel():
    text = SPEC.read_text(encoding="utf-8")
    idx = text.index("Requires:       gnome50-el10-compat")
    before = text[:idx]
    # The nearest %if/%endif pair enclosing this line must be the rhel guard,
    # not left unconditional. Walk backward from idx for the nearest %if.
    if_idx = before.rfind("%if")
    assert if_idx != -1, "gnome50-el10-compat Requires: has no guard at all"
    guard_line = text[if_idx:text.index("\n", if_idx)]
    assert guard_line.strip() == "%if 0%{?rhel}", (
        f"expected the nearest %if above gnome50-el10-compat to be "
        f"'%if 0%{{?rhel}}', got {guard_line.strip()!r} -- unconditional (or "
        f"wrongly-guarded) means this Requires: is unsatisfiable on the "
        f"hummingbird/Fedora-Rawhide target and breaks dnf5 builddep for "
        f"any consumer needing gdm-devel"
    )
    # And the %endif immediately following must close before the next
    # Requires: line (iso-codes), i.e. the guard wraps ONLY this one line.
    endif_idx = text.index("%endif", if_idx)
    between = text[if_idx:endif_idx]
    assert between.count("Requires:") == 1, (
        "the %if 0%{?rhel} guard around gnome50-el10-compat should wrap "
        "exactly that one Requires: line"
    )


def test_gnome_shell_and_iso_codes_stay_unconditional():
    """Sanity check the fix didn't over-guard: these two are real,
    always-needed Requires: and must NOT be inside the rhel-only block."""
    text = SPEC.read_text(encoding="utf-8")
    for line in ("Requires: gnome-shell", "Requires: iso-codes"):
        idx = text.index(line)
        before = text[:idx]
        if_idx = before.rfind("%if")
        endif_idx = before.rfind("%endif")
        assert endif_idx > if_idx or if_idx == -1, (
            f"{line!r} landed inside an %if block -- it must stay "
            f"unconditional on every target"
        )
