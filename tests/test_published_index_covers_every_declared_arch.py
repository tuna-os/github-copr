"""A target that declares an architecture must declare an index for it.

`published_index` is resolved PER ARCH by scripts/published_index.py. A target
that declares two architectures but only one index key therefore hands the
other arch an EMPTY PUBLISHED_INDEX -- no apt/dnf source is written at all, and
every factory-built dependency reads as missing.

That is not hypothetical. ubuntu and debian each declared
`architectures: [amd64, arm64]` with an amd64-only index, so
tideforge-quickshell-ubuntu-arm64 reported

    libcpptrace-dev              NOT AVAILABLE

against a package that was built, published and served for arm64. It looked
like a recipe problem for several rounds. The producer half of the same gap was
publish-tideforge-debs.yml having no arch dimension at all, so nothing arm64
was ever published either.

el10 and hummingbird already declared every arch, which is what made the
omission easy to miss by reading: the file looks consistent until you compare
the two lists key by key.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifests" / "package-factory.yaml"


@pytest.fixture(scope="module")
def targets() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["targets"]


def test_every_declared_arch_has_an_index_where_one_is_declared(targets):
    """Only applies to targets that HAVE a published index: arch and
    opensuse-tumbleweed legitimately have none, and requiring one there would
    invent a repo that does not exist."""
    for name, target in targets.items():
        index = target.get("published_index")
        if not index:
            continue
        missing = [a for a in target.get("architectures", []) if a not in index]
        assert not missing, (name, missing, sorted(index))


def test_the_index_declares_no_arch_the_target_does_not_build(targets):
    """The converse: an index key for an arch the target never builds is dead
    configuration that will drift silently."""
    for name, target in targets.items():
        index = target.get("published_index") or {}
        extra = [a for a in index if a not in target.get("architectures", [])]
        assert not extra, (name, extra)


def test_the_deb_targets_point_both_arches_at_the_same_flat_repo(targets):
    """A flat apt repo serves every architecture from ONE URL -- one pool, one
    Packages, apt selecting on the Architecture field. Giving arm64 a separate
    URL would invent a repository the publisher does not write."""
    for name in ("ubuntu", "debian"):
        index = targets[name]["published_index"]
        assert index["amd64"] == index["arm64"], (name, index)
