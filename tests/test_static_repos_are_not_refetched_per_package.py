"""dnf must not re-fetch a static repo's metadata for every package.

The Rawhide template these mock configs include sets `metadata_expire=0`, and
nothing overrode it. `0` means dnf refuses to trust cached metadata at all, so
every package build in every shard re-downloaded repomd.xml and primary.xml
from every enabled repo.

For `repo.tunaos.org` that is our own Cloudflare Workers bill. 673 packages x
2 arches x 5 bands, per fan-out run; the account reached 76% of its
100,000/day request limit on 2026-08-28 after four runs, with the reset 16
hours away and a live run still building.

WHY `0` IS RIGHT FOR EXACTLY ONE REPO
=====================================

[local-build] is the repo the chain writes into as it builds. build-chain.sh's
MOCK_CACHE_ARGS comment spells out the dependency: the shared root cache holds
only the MINIMAL buildroot, and "BuildRequires resolve after the unpack
against the live repos", which is only true while local-build's metadata is
never cached. Give it an expiry and a package built sixty seconds ago becomes
invisible to the next one -- silently, as a dependency-resolution failure
somewhere down the tier.

So the fix is per-repo, not global, and the assertion below that matters most
is the one pinning local-build at 0.

WHY RAWHIDE IS LEFT ALONE
=========================

It is a rolling repo that genuinely changes mid-run. The static ones cannot:
[hummingbird] is a fixed dated prefix, fedora-44-* is a frozen release, and
[tunaos-hummingbird] changes only when a publish runs -- never during a chain.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = sorted((ROOT / "mock").glob("*.cfg"))

# Repos that cannot change while a chain runs, and why.
STATIC = {
    "hummingbird",
    "tunaos-hummingbird",
    "fedora-44-python",
    "fedora-44-python-updates",
    "fedora-44-perl",
    "fedora-44-perl-updates",
    "fedora-44-mpich",
    "fedora-44-mpich-updates",
}


def repo_blocks(path: Path) -> dict[str, list[str]]:
    """{repo name: its config lines} for every [repo] in the dnf.conf heredoc."""
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\[([a-z0-9._-]+)\]\s*$", line)
        if match:
            current = match.group(1)
            blocks[current] = []
        elif current is not None:
            if line.startswith("config_opts") or line.strip() == '"""':
                current = None
            else:
                blocks[current].append(line)
    return blocks


def setting(lines: list[str], key: str) -> str | None:
    for line in lines:
        match = re.match(rf"^{key}=(.*)$", line.strip())
        if match:
            return match.group(1).strip()
    return None


HUMMINGBIRD = [p for p in CONFIGS if p.name.startswith("hummingbird-ci")]


def test_the_hummingbird_configs_are_present():
    """A glob that silently stops matching passes forever."""
    assert len(HUMMINGBIRD) == 2, [p.name for p in HUMMINGBIRD]


@pytest.mark.parametrize("path", HUMMINGBIRD, ids=lambda p: p.name)
def test_local_build_never_caches_its_metadata(path):
    """THE assertion. local-build grows as the chain builds; caching its
    metadata makes a package built moments ago invisible to the next one."""
    local = repo_blocks(path).get("local-build")
    assert local is not None, f"{path.name} has no [local-build]"
    assert setting(local, "metadata_expire") is None, (
        f"{path.name}: [local-build] must inherit metadata_expire=0. The chain "
        "resolves BuildRequires against this repo WHILE writing into it."
    )


@pytest.mark.parametrize("path", HUMMINGBIRD, ids=lambda p: p.name)
def test_every_static_repo_has_an_expiry(path):
    blocks = repo_blocks(path)
    missing = [
        name for name in sorted(STATIC)
        if name in blocks and setting(blocks[name], "metadata_expire") is None
    ]
    assert not missing, (
        f"{path.name}: {missing} re-fetch metadata for every package. "
        "repo.tunaos.org is our own Cloudflare request budget."
    )


@pytest.mark.parametrize("path", HUMMINGBIRD, ids=lambda p: p.name)
def test_the_published_index_is_covered(path):
    """The one that actually costs money, named explicitly so a future edit
    that drops it from STATIC still fails here."""
    block = repo_blocks(path).get("tunaos-hummingbird")
    assert block is not None, f"{path.name} has no [tunaos-hummingbird]"
    assert "repo.tunaos.org" in "\n".join(block), (
        "this test is pinned to the Cloudflare-served index; if the baseurl "
        "moved, re-point it rather than deleting the assertion"
    )
    assert setting(block, "metadata_expire") is not None


@pytest.mark.parametrize("path", HUMMINGBIRD, ids=lambda p: p.name)
def test_no_file_url_repo_is_given_an_expiry(path):
    """Generalises the local-build rule: a file:// repo is local, mutable and
    free to read, so caching its metadata only ever costs correctness."""
    for name, lines in repo_blocks(path).items():
        baseurl = setting(lines, "baseurl") or ""
        if baseurl.startswith("file://"):
            assert setting(lines, "metadata_expire") is None, (
                f"{path.name}: [{name}] is a local file:// repo and must not "
                "cache metadata"
            )
