"""A cell's action key must depend on every spec its build order builds.

`source_paths` is what makes an edit to a spec change the cell's action key.
If a build order references a path the cell does not list, the cache restores
an ActionResult built from the OLD spec and the edit is silently ignored --
a cache that cannot tell two different recipes apart. Nothing fails; the
wrong package just keeps being served, and the only symptom is that a fix
"did not take".

Measured on 2026-08-26: build-order-hummingbird-desktops.yml built 19
packages out of src/gnome-50/ (gtk4, mutter, gnome-shell, libadwaita, gdm and
the rest of the GNOME stack) while the hummingbird cells listed only
src/hummingbird/ and src/xfce-wayland/. Every one of those 19 specs was
outside the key. The repoint to src/gnome-51/ would have carried the hole
along with the packages.

This is the mirror of #529's property. That one says an edit to ANOTHER
target's inputs must NOT re-key this cell; this one says an edit to THIS
cell's own inputs MUST. Isolation without coverage is just a stale cache.
"""
from __future__ import annotations

import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CELLS = yaml.safe_load(
    (ROOT / "manifests" / "package-builds.yaml").read_text(encoding="utf-8"))


def referenced_paths(manifest: str) -> set[str]:
    """Every `path:` a build order names, as a repo-relative directory."""
    spec = yaml.safe_load((ROOT / manifest).read_text(encoding="utf-8"))
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            path = node.get("path")
            if isinstance(path, str) and path.startswith("src/"):
                found.add(path.rstrip("/") + "/")
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(spec)
    return found


CASES = [
    (cell["id"], cell["manifest"], tuple(cell.get("source_paths") or []))
    for cell in CELLS["native_builds"]
    if (ROOT / cell["manifest"]).is_file()
]


def test_there_are_cells_to_check():
    """A rename of native_builds would make every case below vacuous."""
    assert len(CASES) >= 8, CASES


@pytest.mark.parametrize("cell_id,manifest,source_paths", CASES,
                         ids=[c[0] for c in CASES])
def test_every_path_the_order_builds_is_inside_the_key(
        cell_id, manifest, source_paths):
    uncovered = sorted(
        path for path in referenced_paths(manifest)
        if not any(path.startswith(prefix) for prefix in source_paths))
    assert not uncovered, (
        f"{cell_id} builds these out of {manifest}, but none of its "
        f"source_paths {list(source_paths)} covers them, so editing their "
        f"specs will not re-key the cell and the cache will serve a stale "
        f"build: {uncovered}")


def test_the_check_can_actually_fail():
    """A path outside the listed prefixes must be reported. Without this the
    test above passes just as happily against a walker that finds nothing."""
    hummingbird = next(c for c in CELLS["native_builds"]
                       if c["id"] == "hummingbird-x86_64")
    paths = referenced_paths(hummingbird["manifest"])
    assert paths, "the walker found no paths at all"
    narrowed = ("src/hummingbird/",)
    uncovered = [p for p in paths
                 if not any(p.startswith(x) for x in narrowed)]
    assert uncovered, (
        "dropping src/xfce-wayland/ and src/gnome-51/ from the prefixes "
        "left nothing uncovered, so this check examines nothing")
