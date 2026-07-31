#!/usr/bin/env python3
"""Download a Tideforge source archive and verify its pinned SHA-256."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

import yaml

import tideforge_cache


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="content-addressed store consulted before the network; "
                             "verified downloads are stored for later fetches")
    args = parser.parse_args()
    recipe = yaml.safe_load(args.recipe.read_text())
    sources = tideforge_cache.recipe_sources(recipe)
    for index, source in enumerate(sources):
        if args.cache_dir is not None:
            if tideforge_cache.lookup(args.cache_dir, source["sha256"]) is not None:
                print(f"source {index} verified from cache ({source['sha256'][:12]})")
                continue
        request = Request(source["url"], headers={"User-Agent": "tunaos-package-factory"})
        with urlopen(request) as response:  # nosec B310 - recipe validation requires HTTPS
            if args.cache_dir is None:
                digest = hashlib.file_digest(response, "sha256").hexdigest()
            else:
                payload = response.read()
                digest = hashlib.sha256(payload).hexdigest()
        if digest != source["sha256"]:
            raise SystemExit(f"source {index} checksum mismatch: expected {source['sha256']}, got {digest}")
        if args.cache_dir is not None:
            tideforge_cache.store(args.cache_dir, payload)
    print(f"{recipe['name']}: {len(sources)} source checksum(s) verified")


if __name__ == "__main__":
    main()
