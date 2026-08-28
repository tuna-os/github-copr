"""gnome-desktop3's gtk4 floor must not go stale again.

gnome-desktop3.spec pinned gtk4_version=4.4.0. gnome-desktop's own meson.build
at the exact tag this spec builds -- 51.alpha, not main, which can drift --
declares:

    gtk4_req = '>= 4.12.0'

(fetched from gitlab.gnome.org/GNOME/gnome-desktop at tag 51.alpha). 4.4.0 was
low enough to be satisfied by nearly any gtk4 build in this repo's history,
so the BuildRequires never caught a too-old gtk4 -- exactly the same class of
bug #580's sibling fix (0e716e7, "gtk4 and libadwaita declared floors below
what they need") found and fixed in gtk4.spec and libadwaita.spec. That fix
did not touch gnome-desktop3.spec, so its own floor kept the stale number.

This mirrors test_gtk4_and_libadwaita_floors_match_upstream.py's shape:
one test pins the real floor, one test pins the exact stale value gone for
good (mutation-verified -- reverting to 4.4.0 turns it red).
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "src/gnome-51/gnome-desktop3/gnome-desktop3.spec"


def _global_version(spec: pathlib.Path, name: str) -> tuple[int, ...]:
    text = spec.read_text(encoding="utf-8")
    match = re.search(rf"^%global {re.escape(name)}\s+([0-9.]+)", text, re.MULTILINE)
    assert match, f"no %global {name} in {spec}"
    return tuple(int(part) for part in match.group(1).split("."))


def test_gnome_desktop3_declares_gtk4s_real_floor():
    assert _global_version(SPEC, "gtk4_version") >= (4, 12, 0), (
        "gnome-desktop's own meson.build at tag 51.alpha requires gtk4 >= "
        "4.12.0 (gtk4_req = '>= 4.12.0') -- a lower floor here is satisfiable "
        "by an older gtk4 than this release actually needs"
    )


def test_the_previously_stale_floor_is_gone():
    text = SPEC.read_text(encoding="utf-8")
    assert "%global gtk4_version                      4.4.0" not in text, (
        "gnome-desktop3.spec regressed to the stale gtk4_version=4.4.0 that "
        "let a too-old gtk4 satisfy the BuildRequires"
    )
