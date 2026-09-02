"""The upstream parity audit (#226) is an invariant of the recipe set.

docs/UPSTREAM_PARITY.md registers Bluefin, Aurora and Zirconium as the
upstreams whose curated desktop experiences TunaOS carries forward.  The
snapshots in _upstream-snapshots/ declare every package the register tracks,
and scripts/audit-upstream-parity.py verifies each declaration resolves to a
TunaOS source recipe, a desktop-manifest declaration, a named distribution
package, or an explicit out-of-scope entry with a reason.

These tests pin the enforcement: the committed snapshots must stay covered,
so a recipe rename or removal without a snapshot update is caught here, and
each disposition rule is exercised so the audit cannot silently accept a
declaration the repository does not honour.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / "_upstream-snapshots"

spec = importlib.util.spec_from_file_location(
    "audit_upstream_parity", ROOT / "scripts" / "audit-upstream-parity.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

# Every curated item named by the initial parity inventory in
# docs/UPSTREAM_PARITY.md that has a TunaOS source recipe.
RECIPED_ITEMS = {
    "uupd",            # Bluefin update/store
    "bazaar",          # Bluefin store frontend
    "krunner-bazaar",  # Aurora KDE add-ons
    "oversteer-udev",
    "kairpods",
    "plasma-setup",
    "niri",            # Zirconium Niri/DMS
    "quickshell",
    "dms",
    "dms-cli",
    "dms-greeter",
    "iio-niri",
    "dgop",
    "danksearch",
    "dankcalendar",
}


def recipes() -> dict[str, str]:
    return audit.recipe_index(ROOT)


def manifests() -> set[str]:
    return audit.manifest_names(ROOT)


def report() -> dict:
    return audit.audit_all(SNAPSHOTS, ROOT)


def test_committed_snapshots_are_fully_covered() -> None:
    r = report()
    assert r["summary"]["gaps"] == 0, (
        f"{r['summary']['gaps']} upstream declaration(s) do not resolve "
        "against this repository; fix the snapshot or the recipe set"
    )


def test_every_snapshot_declares_an_upstream_revision() -> None:
    for path in sorted(SNAPSHOTS.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        assert data.get("revision"), f"{path.name}: snapshot has no upstream revision"
        assert data.get("packages"), f"{path.name}: snapshot declares no packages"


def test_register_items_resolve_to_source_recipes() -> None:
    index = recipes()
    missing = sorted(RECIPED_ITEMS - set(index))
    assert not missing, (
        "parity inventory items have no TunaOS recipe: "
        f"{missing}"
    )


def test_out_of_scope_entries_carry_reasons() -> None:
    r = report()
    for snapshot in r["snapshots"].values():
        for package in snapshot["packages"]:
            if package["disposition"] == "out-of-scope":
                assert package["provenance"] == "out-of-scope", package["name"]
                entry_ok = any(
                    p["name"] == package["name"] and p.get("reason")
                    for p in yaml.safe_load(
                        (SNAPSHOTS / f"{snapshot['flavor']}.yaml").read_text()
                    )["packages"]
                )
                assert entry_ok, f"{snapshot['flavor']}:{package['name']} lacks a reason"


def test_spec_trees_count_as_recipes() -> None:
    index = recipes()
    assert index["SwayNotificationCenter"] == "src/hummingbird/SwayNotificationCenter"
    assert index["xfwl4"].startswith("src/xfce-wayland/")


def snapshot(**overrides) -> dict:
    data = {
        "upstream": "test-upstream",
        "flavor": "test",
        "revision": "0000",
        "snapshotted_at": "2026-08-11",
        "scope": "test",
        "packages": [],
    }
    data.update(overrides)
    return data


def test_a_declaration_with_no_disposition_is_a_gap() -> None:
    result = audit.audit_snapshot(
        snapshot(packages=[{"name": "x", "source": "upstream"}]),
        recipes(),
        manifests(),
    )
    assert result["gaps"][0]["name"] == "x"


def test_a_recipe_declaration_without_a_recipe_is_a_gap() -> None:
    result = audit.audit_snapshot(
        snapshot(packages=[{"name": "does-not-exist", "disposition": "recipe"}]),
        recipes(),
        manifests(),
    )
    assert "no packages/does-not-exist/package.yaml" in result["gaps"][0]["issues"][0]


def test_a_distro_declaration_must_name_the_distribution() -> None:
    result = audit.audit_snapshot(
        snapshot(packages=[{"name": "cage", "disposition": "distro"}]),
        recipes(),
        manifests(),
    )
    assert "must name the owning distribution" in result["gaps"][0]["issues"][0]

    ok = audit.audit_snapshot(
        snapshot(packages=[{"name": "cage", "disposition": "distro", "distro": "fedora"}]),
        recipes(),
        manifests(),
    )
    assert ok["gaps"] == []


def test_an_out_of_scope_declaration_must_carry_a_reason() -> None:
    result = audit.audit_snapshot(
        snapshot(packages=[{"name": "sunshine", "disposition": "out-of-scope"}]),
        recipes(),
        manifests(),
    )
    assert "must carry a reason" in result["gaps"][0]["issues"][0]
