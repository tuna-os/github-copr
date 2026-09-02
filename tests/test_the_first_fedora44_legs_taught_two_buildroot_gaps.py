"""The first hummingbird legs on the Fedora 44 root (run 33597624514, PR
#630) failed three packages, two ways, neither of which the root caused
and both of which it must answer for:

  * langtable, on every leg since the first (also main's Rawhide-root leg,
    run 33580878734): its %check validates five data files with xmllint,
    and Fedora's spec names no libxml2 because Koji's buildroot happens
    to carry it.  Hummingbird's does not.

  * python-dbus-next and python-aiohappyeyeballs, aarch64 only because
    x86_64 deferred them: Fedora 44's python3-pytest-asyncio 1.1.0
    requires pytest < 9 and Hummingbird ships pytest 9.1.1; mock's best=1
    refuses to settle for the 8.4.2 beside it, and builddep dies before
    rpmbuild starts.

The fixes are a vendored langtable spec that differs from Fedora's by one
BuildRequires, and a bootstrap tier that builds Rawhide's pytest-asyncio
(pytest < 10) so local-build masks Fedora 44's by name.  These tests pin
both to the files the chain reads, so a regeneration or a tidy-up cannot
quietly put either failure back.
"""
from __future__ import annotations

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
ORDER = ROOT / "build-order-hummingbird-desktops.yml"
CATALOG = ROOT / "manifests" / "hummingbird-desktops.yaml"
LANGTABLE = ROOT / "src" / "hummingbird" / "langtable"


def tiers() -> list[dict]:
    return yaml.safe_load(ORDER.read_text(encoding="utf-8"))["tiers"]


def entries() -> dict[str, tuple[str, dict]]:
    """package name -> (tier name, entry)."""
    out = {}
    for tier in tiers():
        for pkg in tier["packages"]:
            out[pkg.get("distgit") or pkg["path"].rsplit("/", 1)[-1]] = (tier["name"], pkg)
    return out


def test_langtable_names_the_xmllint_its_check_runs():
    spec = (LANGTABLE / "langtable.spec").read_text(encoding="utf-8")
    assert re.search(r"^BuildRequires:\s+libxml2\s*$", spec, re.M), (
        "langtable's %check calls xmllint five times; without libxml2 in "
        "BuildRequires the Hummingbird buildroot has no /usr/bin/xmllint"
    )
    assert spec.count("xmllint --noout --relaxng") == 5, "the %check this BuildRequires serves"
    # Otherwise Fedora's packaging: same Source0, same %check, a real sources
    # pin so build-chain.sh verifies the tarball it downloads.
    assert "Source0:        https://github.com/mike-fabian/langtable/releases/download/" in spec
    sources = (LANGTABLE / "sources").read_text(encoding="utf-8")
    assert re.fullmatch(r"SHA512 \(langtable-[\d.]+\.tar\.gz\) = [0-9a-f]{128}\n", sources)


def test_langtable_is_built_from_the_vendored_spec_not_reimported():
    """A `distgit:` key would make run-package-factory-cell.sh import
    Fedora's spec over the vendored one and lose the BuildRequires."""
    order = entries()
    if "langtable" not in order:
        # Only the bluefin parity desktop reaches langtable; with GNOME
        # consumed from utah-packages it can drop out of the order entirely,
        # and then there is nothing to re-import.  The vendored spec stays
        # for the day a root pulls it back in.
        pytest.skip("langtable is not in the current build order")
    tier, entry = order["langtable"]
    assert entry["path"] == "src/hummingbird/langtable"
    assert "distgit" not in entry, entry
    assert tier.startswith("layer-")


def test_pytest_asyncio_is_built_before_the_first_layer():
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    declared = {
        p.get("distgit") or p["path"].rsplit("/", 1)[-1]: t["name"]
        for t in catalog["bootstrap"] for p in t["packages"]
    }
    assert declared.get("python-pytest-asyncio", "").startswith("bootstrap-"), (
        "python-pytest-asyncio must be declared in the catalog's bootstrap "
        "tiers, or the next regeneration drops it"
    )
    order = entries()
    tier, entry = order["python-pytest-asyncio"]
    assert tier == declared["python-pytest-asyncio"]
    assert entry.get("distgit") == "python-pytest-asyncio", "Rawhide's 1.4.0 (pytest < 10), not a vendored copy"
    names = [t["name"] for t in tiers()]
    assert names.index(tier) < names.index("layer-00")
    for needer in ("python-dbus-next", "python-aiohappyeyeballs"):
        assert needer in order and names.index(order[needer][0]) > names.index(tier), needer


def test_a_bootstrap_package_is_not_emitted_twice():
    seen = [n for t in tiers() for n in
            (p.get("distgit") or p["path"].rsplit("/", 1)[-1] for p in t["packages"])]
    assert seen.count("python-pytest-asyncio") == 1


def test_the_reason_travels_with_the_declaration():
    text = CATALOG.read_text(encoding="utf-8")
    block = text[text.index("bootstrap-03"):text.index("bootstrap-04")]
    assert "pytest < 9" in block and "33597624514" in block, (
        "the bootstrap-04 comment must say why a test tool sits among the "
        "PEP-517 backends, with the run that showed it"
    )
