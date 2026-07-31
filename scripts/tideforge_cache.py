#!/usr/bin/env python3
"""Content-addressed store for Tideforge source archives.

Blobs live at ``<cache_dir>/<sha256>``. The pinned recipe checksum is both
the lookup key and the integrity proof, so a hit is provably the recipe's
bytes and a corrupted entry is indistinguishable from a miss. The ``key``
subcommand prints a digest over a recipe's pinned checksums — the same
value on every build target, changing exactly when a source pin changes —
for use as an actions/cache key.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    key = subparsers.add_parser("key", help="print the cache key for a recipe")
    key.add_argument("recipe", type=Path)
    args = parser.parse_args()
    print(cache_key(yaml.safe_load(args.recipe.read_text())))


if __name__ == "__main__":
    main()
