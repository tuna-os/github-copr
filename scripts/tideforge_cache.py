#!/usr/bin/env python3
"""Content-addressed store for Tideforge source archives.

Blobs live at ``<cache_dir>/<sha256>``. The pinned recipe checksum is both
the lookup key and the integrity proof, so a hit is provably the recipe's
bytes and a corrupted entry is indistinguishable from a miss. The ``key``
subcommand prints a digest over a recipe's pinned checksums — the same
value on every build target, changing exactly when a source pin changes —
for use as an actions/cache key.

The ``oras_lookup`` and ``oras_push`` helpers add a second cache layer on
ghcr.io that survives actions/cache eviction.  An ORAS pull is attempted
after a local-cache miss and validated through the same re-hash-on-read
check, so a corrupted remote artifact reads as a miss.  Push failure is
non-fatal: a cache that can fail the build is worse than no cache.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import subprocess
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)
ORAS_REPO = "ghcr.io/tuna-os/tideforge-sources"
# Set by CI; anonymous pulls work for public packages so this is only
# required for push (the seed workflow on main sets it).
ORAS_PUSH_ENABLED = os.environ.get("TIDEFORGE_ORAS_PUSH", "") == "1"


def recipe_sources(recipe: dict) -> list[dict]:
    return [recipe["source"], *recipe.get("sources", [])]


def cache_key(recipe: dict) -> str:
    digests = sorted(source["sha256"] for source in recipe_sources(recipe))
    return hashlib.sha256("\n".join(digests).encode()).hexdigest()


def lookup(cache_dir: Path, sha256: str) -> bytes | None:
    blob = cache_dir / sha256
    if not blob.is_file():
        return None
    payload = blob.read_bytes()
    if hashlib.sha256(payload).hexdigest() != sha256:
        blob.unlink()
        return None
    return payload


def store(cache_dir: Path, payload: bytes) -> Path:
    digest = hashlib.sha256(payload).hexdigest()
    cache_dir.mkdir(parents=True, exist_ok=True)
    staging = cache_dir / f".{digest}.tmp"
    staging.write_bytes(payload)
    staging.replace(cache_dir / digest)
    return cache_dir / digest


def oras_pull(cache_dir: Path, sha256: str) -> bool:
    """Pull a blob from the ORAS registry into the CAS directory.

    Returns True when the pull succeeds *and* the blob validates via
    ``lookup``.  A corrupted remote artifact, a missing tag, or an
    unreachable registry all return False — the caller falls back to
    the normal network download.
    """
    tag = f"{ORAS_REPO}:{sha256}"
    try:
        subprocess.run(
            ["oras", "pull", "--plain-http=false", tag, "--output", str(cache_dir)],
            check=True, capture_output=True, text=True, timeout=60,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return lookup(cache_dir, sha256) is not None


def oras_push(cache_dir: Path, sha256: str) -> bool:
    """Push a CAS blob to the ORAS registry.

    Returns True on success.  Failure is non-fatal: the build must not
    break because a cache push failed.
    """
    if not ORAS_PUSH_ENABLED:
        return False
    blob = cache_dir / sha256
    if not blob.is_file():
        return False
    tag = f"{ORAS_REPO}:{sha256}"
    try:
        subprocess.run(
            ["oras", "push", "--plain-http=false", tag, str(blob)],
            check=True, capture_output=True, text=True, timeout=60,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def oras_lookup(cache_dir: Path, sha256: str) -> bytes | None:
    """Look up a blob in the CAS, falling back to an ORAS pull on miss.

    The local filesystem cache (actions/cache) is always consulted first.
    When it misses, an ORAS pull from ghcr.io is attempted before the
    caller resorts to a network download.  The same re-hash-on-read check
    validates whatever arrives, so a corrupt remote artifact reads as a
    miss and the caller proceeds to download from the pinned URL normally.
    """
    payload = lookup(cache_dir, sha256)
    if payload is not None:
        return payload
    if oras_pull(cache_dir, sha256):
        logger.info("source %s: ORAS cache hit", sha256[:12])
        return lookup(cache_dir, sha256)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    key = subparsers.add_parser("key", help="print the cache key for a recipe")
    key.add_argument("recipe", type=Path)
    args = parser.parse_args()
    print(cache_key(yaml.safe_load(args.recipe.read_text())))


if __name__ == "__main__":
    main()
