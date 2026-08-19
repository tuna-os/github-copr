#!/usr/bin/env python3
"""Emit the one package-factory matrix from recipes and native queue data."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

import yaml


RECIPE_CHANGE = re.compile(r"^packages/([^/]+)/")
COMMON_INPUTS = {
    ".github/workflows/package-factory.yml",
    "scripts/run-package-factory-cell.sh",
    "scripts/verify-package-factory-cell.sh",
    "scripts/tideforge.py",
}
FORMAT_INPUTS = {
    "scripts/assemble-deb-source-tree.py": {"deb"},
    "scripts/build-chain.sh": {"rpm"},
    "scripts/arch-clean-install.sh": {"pkg.tar.zst"},
}


def load_yaml(path: pathlib.Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def runner_for(architecture: str) -> str:
    return "ubuntu-24.04-arm" if architecture in {"aarch64", "arm64"} else "ubuntu-24.04"


def tideforge_cells(root: pathlib.Path) -> list[dict[str, Any]]:
    factory = load_yaml(root / "manifests/package-factory.yaml")
    cells = []
    for recipe_path in sorted((root / "packages").glob("*/package.yaml")):
        recipe = load_yaml(recipe_path)
        package = str(recipe.get("name") or recipe_path.parent.name)
        for target_id in recipe.get("targets") or []:
            target = (factory.get("targets") or {}).get(target_id)
            if not isinstance(target, dict):
                raise ValueError(f"{recipe_path}: unknown target {target_id}")
            image = target.get("probe_image")
            package_format = target.get("format")
            if not image or not package_format:
                raise ValueError(f"{recipe_path}: incomplete target contract {target_id}")
            architectures = target.get("architectures") or []
            for architecture in architectures:
                # Arch's official container is x86_64-only. The target contract
                # may advertise future aarch64 support, but no action is emitted
                # until it declares a target-native image for that architecture.
                if target_id == "arch" and architecture != "x86_64":
                    continue
                cells.append(
                    {
                        "id": f"tideforge-{package}-{target_id}-{architecture}",
                        "engine": "tideforge",
                        "package": package,
                        "recipe": recipe_path.relative_to(root).as_posix(),
                        "target": target_id,
                        "format": package_format,
                        "architecture": architecture,
                        "image": image,
                        "runner": runner_for(str(architecture)),
                        "source_paths": [recipe_path.parent.relative_to(root).as_posix() + "/"],
                    }
                )
    return cells


def native_cells(root: pathlib.Path) -> list[dict[str, Any]]:
    registry = load_yaml(root / "manifests/package-builds.yaml")
    cells = []
    for raw in registry.get("native_builds") or []:
        if not isinstance(raw, dict):
            raise ValueError("native build entries must be mappings")
        cell = dict(raw)
        required = {"id", "target", "architecture", "image", "manifest", "mock_config", "source_paths"}
        missing = sorted(required - cell.keys())
        if missing:
            raise ValueError(f"native build {cell.get('id', '<unknown>')} misses {missing}")
        cell.update(
            {
                "engine": "build-chain",
                "format": "rpm",
                "runner": cell.get("runner") or runner_for(str(cell["architecture"])),
            }
        )
        cells.append(cell)
    return cells


def all_cells(root: pathlib.Path) -> list[dict[str, Any]]:
    cells = tideforge_cells(root) + native_cells(root)
    ids = [cell["id"] for cell in cells]
    if len(ids) != len(set(ids)):
        raise ValueError("package factory cell IDs must be unique")
    return sorted(cells, key=lambda cell: cell["id"])


def affected_formats(changed: set[str]) -> set[str] | None:
    if changed & COMMON_INPUTS:
        return None
    formats = set()
    for path, selected in FORMAT_INPUTS.items():
        if path in changed:
            formats.update(selected)
    return formats


def select_cells(cells: list[dict[str, Any]], changed_files: list[str] | None) -> list[dict[str, Any]]:
    if changed_files is None:
        return cells
    changed = {path.strip() for path in changed_files if path.strip()}
    if not changed:
        return []
    if "manifests/package-factory.yaml" in changed or "manifests/package-builds.yaml" in changed:
        return cells
    formats = affected_formats(changed)
    if formats is None:
        return cells
    changed_packages = {match.group(1) for path in changed if (match := RECIPE_CHANGE.match(path))}
    selected = []
    for cell in cells:
        if cell["engine"] == "tideforge" and cell["package"] in changed_packages:
            selected.append(cell)
            continue
        if formats and cell["format"] in formats:
            selected.append(cell)
            continue
        if cell["engine"] == "build-chain" and any(
            path == cell["manifest"] or any(path.startswith(prefix) for prefix in cell["source_paths"])
            for path in changed
        ):
            selected.append(cell)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."))
    parser.add_argument("--changed-files", type=pathlib.Path)
    parser.add_argument("--cell", help="optional exact cell ID for a manual run")
    parser.add_argument("--github-output", type=pathlib.Path)
    args = parser.parse_args()
    try:
        cells = all_cells(args.root)
        changed = None
        if args.changed_files:
            changed = args.changed_files.read_text(encoding="utf-8").splitlines()
        selected = select_cells(cells, changed)
        if args.cell:
            selected = [cell for cell in cells if cell["id"] == args.cell]
            if not selected:
                raise ValueError(f"unknown package factory cell: {args.cell}")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"package-factory planner failed closed: {exc}", file=sys.stderr)
        return 2
    shards = [selected[index:index + 200] for index in range(0, len(selected), 200)] or [[]]
    while len(shards) < 3:
        shards.append([])
    if len(shards) > 3:
        print("package-factory planner exceeded three 200-cell shards", file=sys.stderr)
        return 2
    matrices = [json.dumps({"include": shard}, separators=(",", ":")) for shard in shards]
    print(json.dumps({"count": len(selected), "matrices": matrices}))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"count={len(selected)}\n")
            for index, matrix in enumerate(matrices):
                output.write(f"matrix_{index}={matrix}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
