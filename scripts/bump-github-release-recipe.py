#!/usr/bin/env python3
"""Atomically update a Tideforge recipe to an upstream stable GitHub release."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

import yaml


def get(url: str) -> bytes:
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "tunaos-package-factory"})
    with urlopen(request) as response:  # nosec B310 - URLs are constructed below
        return response.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--repo", required=True, help="GitHub owner/repository")
    args = parser.parse_args()
    recipe = yaml.safe_load(args.recipe.read_text())
    release = json.loads(get(f"https://api.github.com/repos/{args.repo}/releases/latest"))
    if release.get("prerelease") or release.get("draft"):
        raise SystemExit("latest GitHub release is not stable")
    tag = release["tag_name"]
    version = tag.removeprefix("v")
    source_url = f"https://github.com/{args.repo}/archive/refs/tags/{tag}.tar.gz"
    checksum = hashlib.sha256(get(source_url)).hexdigest()
    if recipe["version"] == version and recipe["source"]["sha256"] == checksum:
        print("Recipe already tracks latest stable release")
        return
    recipe["version"] = version
    recipe["source"]["url"] = source_url
    recipe["source"]["sha256"] = checksum
    recipe["source"]["directory"] = f"{recipe['name']}-{version}"
    args.recipe.write_text(yaml.safe_dump(recipe, sort_keys=False))
    print(f"Updated {args.recipe} to {tag}")


if __name__ == "__main__":
    main()
