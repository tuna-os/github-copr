"""The tier selection has to find the tiers a desktop needs, not the tiers
named after it.

The regression these pin is quiet by construction: selecting `xfce-*` for XFCE
returns a non-empty list, builds it, and succeeds, having attempted 9 of the
248 source packages XFCE needs. Nothing in the run says so. So the tests here
care less about the happy path than about the two ways the answer can be wrong
without looking wrong -- a short list, and a list that silently drops packages
the manifest never placed.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "select-desktop-tiers.py"
MANIFEST = REPO / "build-order-hummingbird-desktops.yml"
GAP = REPO / "docs" / "hummingbird-desktop-gap.json"

sys.path.insert(0, str(REPO / "scripts"))


def _select(**kw):
    import importlib.util

    spec = importlib.util.spec_from_file_location("sdt", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _select()


def tiers(names_to_packages):
    return {
        "tiers": [
            {"name": n, "packages": [{"path": f"src/x/{p}", "distgit": p} for p in ps]}
            for n, ps in names_to_packages
        ]
    }


def report(**desktops):
    return {"desktops": {d: {"source_packages_to_build": ps} for d, ps in desktops.items()}}


def test_picks_tiers_by_content_not_by_name():
    m = tiers([
        ("bootstrap-00", ["flit"]),
        ("gnome-00", ["glib", "gtk"]),
        ("xfce-00", ["xfwm"]),
    ])
    r = report(xfce=["glib", "xfwm"])
    # glib lives in a gnome-* tier and XFCE needs it.
    assert MOD.select(m, r, "xfce") == ["bootstrap-00", "gnome-00", "xfce-00"]


def test_name_prefix_alone_would_have_missed_most_of_it():
    """The specific shape of the bug, stated as a test rather than a comment."""
    m = tiers([
        ("gnome-00", ["a", "b", "c"]),
        ("xfce-00", ["d"]),
    ])
    r = report(xfce=["a", "b", "c", "d"])
    selected = MOD.select(m, r, "xfce")
    by_name = [n for n in ("gnome-00", "xfce-00") if n.startswith("xfce-")]
    assert selected == ["gnome-00", "xfce-00"]
    assert by_name == ["xfce-00"]  # what the old selection returned


def test_unplaced_package_is_an_error_not_a_shorter_list():
    m = tiers([("gnome-00", ["glib"])])
    r = report(xfce=["glib", "never-packaged"])
    with pytest.raises(SystemExit) as e:
        MOD.select(m, r, "xfce")
    assert "never-packaged" in str(e.value)


def test_explicit_tiers_are_verbatim_including_bootstrap():
    m = tiers([("bootstrap-00", ["flit"]), ("gnome-00", ["glib"])])
    r = report(gnome=["glib"])
    assert MOD.select(m, r, "gnome", requested=["gnome-00"]) == ["gnome-00"]


def test_unknown_explicit_tier_is_rejected():
    m = tiers([("gnome-00", ["glib"])])
    with pytest.raises(SystemExit):
        MOD.select(m, report(gnome=["glib"]), "gnome", requested=["gnome-99"])


def test_selection_keeps_manifest_order():
    """Manifest order *is* build order. Tier names sort in an order that has
    nothing to do with it -- cosmic-00 depends on gnome-00 and sorts before
    it -- so anything that normalises the list breaks the builds downstream
    of it rather than the selection itself."""
    m = tiers([
        ("bootstrap-00", ["flit"]),
        ("gnome-00", ["a"]),
        ("cosmic-00", ["b"]),
        ("niri-00", ["c"]),
        ("kde-00", ["d"]),
    ])
    r = report(kde=["d", "a", "b", "c"])
    got = MOD.select(m, r, "kde")
    assert got == ["bootstrap-00", "gnome-00", "cosmic-00", "niri-00", "kde-00"]
    assert got != sorted(got)


def test_exclude_splits_a_shared_trunk_off():
    m = tiers([
        ("bootstrap-00", ["flit"]),
        ("gnome-00", ["a"]),
        ("kde-00", ["c"]),
    ])
    r = report(kde=["a", "c"])
    full = MOD.select(m, r, "kde")
    rest = MOD.select(m, r, "kde", exclude=["bootstrap-00", "gnome-00"])
    assert full == ["bootstrap-00", "gnome-00", "kde-00"]
    assert rest == ["kde-00"]


def test_packages_without_distgit_are_named_by_path():
    m = {"tiers": [{"name": "gnome-00", "packages": [{"path": "src/deps/libebur128"}]}]}
    r = report(gnome=["libebur128"])
    assert MOD.select(m, r, "gnome") == ["gnome-00"]


def test_every_desktop_in_the_real_manifest_resolves_completely():
    """No package any desktop needs may be absent from the manifest."""
    m = yaml.safe_load(MANIFEST.read_text())
    r = json.loads(GAP.read_text())
    contents = {t["name"]: MOD.tier_packages(t) for t in m["tiers"]}
    for desktop in r["desktops"]:
        selected = MOD.select(m, r, desktop)  # raises if anything is unplaced
        covered = set().union(*(contents[n] for n in selected))
        need = set(r["desktops"][desktop]["source_packages_to_build"])
        assert need <= covered, desktop
        named = [n for n in selected if n.startswith(desktop + "-")]
        assert len(selected) > len(named), (
            f"{desktop} resolved to only its own tiers -- either the manifest "
            "stopped deduplicating or the selection regressed to a prefix match"
        )


def test_cli_prints_a_comma_separated_list():
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(MANIFEST),
         "--gap-report", str(GAP), "--desktop", "xfce"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert out.startswith("bootstrap-00,")
    assert "," in out and " " not in out
