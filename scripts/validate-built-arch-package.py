#!/usr/bin/env python3
"""Validate an Arch package artifact against the runtime contract in a recipe."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def field(info: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}\s*:\s*(.+)$", info, re.MULTILINE)
    if not match:
        fail(f"built package metadata is missing {name}")
    return match.group(1).strip()


def dependency_names(values: list[str]) -> set[str]:
    return {re.split(r"[<>=: ]", value, maxsplit=1)[0] for value in values}


def validate(recipe: dict, info: str) -> None:
    if field(info, "Name") != recipe["name"]:
        fail("built package name does not match recipe")
    if not field(info, "Version").startswith(f"{recipe['version']}-"):
        fail("built package version does not match recipe")
    if field(info, "Architecture") not in {"x86_64", "aarch64"}:
        fail("built package has an unsupported architecture")
    runtime = recipe.get("dependencies", {}).get("runtime", {})
    declared = dependency_names(list(runtime.get("common", [])) + list(runtime.get("targets", {}).get("arch", [])))
    built = dependency_names(field(info, "Depends On").split())
    missing = declared - built
    if missing:
        fail(f"built package is missing declared runtime dependencies: {sorted(missing)}")
    print("Built Arch package: valid")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("recipe", type=Path)
    parser.add_argument("package_info", type=Path)
    args = parser.parse_args()
    recipe = yaml.safe_load(args.recipe.read_text())
    if not isinstance(recipe, dict):
        fail("recipe must be a mapping")
    validate(recipe, args.package_info.read_text())


if __name__ == "__main__":
    main()
