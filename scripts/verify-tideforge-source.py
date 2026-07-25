#!/usr/bin/env python3
"""Download a Tideforge source archive and verify its pinned SHA-256."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

import yaml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("recipe", type=Path)
    args = parser.parse_args()
    recipe = yaml.safe_load(args.recipe.read_text())
    source = recipe["source"]
    request = Request(source["url"], headers={"User-Agent": "tunaos-package-factory"})
    with urlopen(request) as response:  # nosec B310 - recipe validation requires HTTPS
        digest = hashlib.file_digest(response, "sha256").hexdigest()
    if digest != source["sha256"]:
        raise SystemExit(f"checksum mismatch: expected {source['sha256']}, got {digest}")
    print(f"{recipe['name']}: source checksum verified")


if __name__ == "__main__":
    main()
