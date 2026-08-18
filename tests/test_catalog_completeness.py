"""RFC 011 Phase 0: the catalog must be complete, and completeness must be
a CI failure, not a memory.

manifests/catalog.yaml indexes every package any factory family builds. The
sources of executed truth it must stay in mutual coverage with are the
build-order*.yml files, the tideforge workflow matrices, and the target
queues. scripts/build-catalog.py regenerates the catalog from those sources;
these tests fail the moment either side moves without the other.

The trap this kills is documented in docs/PACKAGE_FACTORY.md: a package
present under packages/ but in no matrix is never built, silently. The
bootstrap measured exactly three such orphans; that list may shrink, never
grow.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOG = ROOT / "manifests" / "catalog.yaml"
FACTORY = ROOT / "manifests" / "package-factory.yaml"

# The three recipes that existed under packages/ with no matrix, queue, or
# build order referencing them at bootstrap (2026-08-18). Deliberate
# allowlist: removing an entry (because the recipe gained a matrix cell or
# was deleted) is progress; adding one is the defect class this file exists
# to prevent.
KNOWN_ORPHAN_RECIPES = {"cpptrace-devel", "gtkgreet", "iio-niri"}


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_catalog", ROOT / "scripts" / "build-catalog.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _catalog() -> dict:
    return yaml.safe_load(CATALOG.read_text(encoding="utf-8"))


def test_catalog_matches_regeneration() -> None:
    """The committed catalog IS the collector's output over the executed
    sources. Any build-order edit, matrix edit, or queue edit that is not
    re-cataloged fails here — in both directions."""
    mod = _load_builder()
    regenerated = mod.collect()
    committed = {(p["name"], p["family"]): p for p in _catalog()["packages"]}

    regen_keys = set(regenerated)
    committed_keys = set(committed)
    missing = sorted(regen_keys - committed_keys)
    stale = sorted(committed_keys - regen_keys)
    assert not missing, f"executed but not cataloged: {missing[:10]}"
    assert not stale, f"cataloged but no longer executed: {stale[:10]}"

    for key, regen in regenerated.items():
        entry = committed[key]
        assert sorted(regen["targets"]) == entry["targets"], key
        assert sorted(regen["referenced_by"]) == entry["referenced_by"], key


def test_targets_are_declared_in_the_factory_contract() -> None:
    """A catalog entry may only name targets package-factory.yaml declares.
    This is the rule that surfaced the fedora-44 gap at bootstrap: the XFWL4
    Fedora family had been publishing to a target the contract never named.
    """
    declared = set(yaml.safe_load(
        FACTORY.read_text(encoding="utf-8"))["targets"])
    for p in _catalog()["packages"]:
        rogue = set(p["targets"]) - declared
        assert not rogue, (
            f"{p['name']} ({p['family']}) names undeclared target(s) "
            f"{sorted(rogue)}; declare them in manifests/package-factory.yaml "
            f"or fix the order/queue")


def test_executed_packages_have_recorded_provenance() -> None:
    """Phase 0's gate: every package a build order or workflow matrix
    actually executes has a recorded upstream (a version+source, a distgit
    ref — the pin mechanism for snapshot rebuilds — or a COPR source) and a
    packaging ref. Queue-only entries are declared intent, not executed
    builds, and are exempt until a matrix picks them up."""
    for p in _catalog()["packages"]:
        executed = any(not r.startswith("manifests/target-queues/")
                       for r in p["referenced_by"])
        if not executed:
            continue
        packaging = p.get("packaging") or {}
        has_payload = any(
            isinstance(pk, dict) and (
                pk.get("native") or pk.get("tideforge") or pk.get("distgit")
                or pk.get("copr"))
            for pk in packaging.values())
        assert has_payload, f"{p['name']} ({p['family']}) has no payload ref"
        up = p.get("upstream") or {}
        rpm = packaging.get("rpm") or {}
        assert up.get("distgit") or up.get("version") or up.get("source") \
            or rpm.get("copr"), (
                f"{p['name']} ({p['family']}) is executed but records no "
                f"upstream provenance")


def test_payload_paths_exist_on_disk() -> None:
    for p in _catalog()["packages"]:
        for pk in (p.get("packaging") or {}).values():
            if not isinstance(pk, dict) or pk.get("missing_on_disk"):
                continue
            for kind in ("native", "tideforge"):
                ref = pk.get(kind)
                if ref:
                    assert (ROOT / ref).is_dir(), (
                        f"{p['name']} ({p['family']}): {kind} payload "
                        f"{ref} is not a directory")


def test_orphan_recipes_cannot_grow() -> None:
    """Every packages/<recipe> is referenced by the catalog except the
    bootstrap-measured allowlist. A new unreferenced recipe is the
    'present under packages/ but in no matrix -> never built' trap."""
    referenced = set()
    for p in _catalog()["packages"]:
        for pk in (p.get("packaging") or {}).values():
            if isinstance(pk, dict) and pk.get("tideforge"):
                referenced.add(pk["tideforge"].split("/", 1)[1])
    ondisk = {d.name for d in (ROOT / "packages").iterdir()
              if d.is_dir() and not d.name.startswith("_")}
    orphans = ondisk - referenced
    new_orphans = orphans - KNOWN_ORPHAN_RECIPES
    assert not new_orphans, (
        f"recipe(s) exist under packages/ but nothing builds them: "
        f"{sorted(new_orphans)} — add a matrix/queue cell or delete the "
        f"recipe (docs/PACKAGE_FACTORY.md trap)")
    healed = KNOWN_ORPHAN_RECIPES - orphans
    assert not healed, (
        f"{sorted(healed)} are no longer orphans — remove them from "
        f"KNOWN_ORPHAN_RECIPES so the allowlist only shrinks")
