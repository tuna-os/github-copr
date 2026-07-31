#!/usr/bin/env python3
"""Fetch every checksum-locked Tideforge archive using its rendered name."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml


def filename(source: dict) -> str:
    value = source.get("filename") or Path(urlparse(source["url"]).path).name
    if not value or Path(value).name != value:
        raise SystemExit("invalid Tideforge source filename")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("recipe", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    recipe = yaml.safe_load(args.recipe.read_text())
    args.destination.mkdir(parents=True, exist_ok=True)
    for source in [recipe["source"], *recipe.get("sources", [])]:
        request = Request(source["url"], headers={"User-Agent": "tunaos-package-factory"})
        payload = urlopen(request).read()  # nosec B310 - schema validates pinned HTTPS sources
        digest = hashlib.sha256(payload).hexdigest()
        if digest != source["sha256"]:
            raise SystemExit(f"checksum mismatch for {source['url']}")
        (args.destination / filename(source)).write_bytes(payload)


if __name__ == "__main__":
    main()
