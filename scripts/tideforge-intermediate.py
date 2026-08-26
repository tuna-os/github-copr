#!/usr/bin/env python3
"""Theory prototype: seal one staged payload for cheap native repackaging.

This is deliberately not wired into the package factory.  It explores the
boundary between an expensive upstream build/install and the comparatively
cheap, target-specific package metadata step.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile
import tempfile

import yaml


SCHEMA = 0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_path(path: str) -> str:
    value = str(PurePosixPath(path)).lstrip("/")
    if not value or value == "." or ".." in PurePosixPath(value).parts:
        raise SystemExit(f"unsafe payload path: {path!r}")
    return value


def elf_contract(path: Path) -> dict | None:
    if not path.is_file() or path.is_symlink():
        return None
    with path.open("rb") as stream:
        magic = stream.read(4)
    if magic != b"\x7fELF":
        return None
    proc = subprocess.run(
        ["readelf", "--wide", "--dynamic", "--version-info", str(path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    needed: list[str] = []
    versions: set[str] = set()
    for line in proc.stdout.splitlines():
        if "(NEEDED)" in line and "[" in line:
            needed.append(line.rsplit("[", 1)[1].split("]", 1)[0])
        for token in line.replace("(", " ").replace(")", " ").split():
            if token.startswith(("GLIBC_", "GLIBCXX_", "CXXABI_")):
                versions.add(token.rstrip("[]"))
    return {"needed": sorted(set(needed)), "symbol_versions": sorted(versions)}


def inventory(root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(root.rglob("*")):
        relative = normalized_path(path.relative_to(root).as_posix())
        mode = stat.S_IMODE(path.lstat().st_mode)
        if path.is_symlink():
            rows.append({"path": relative, "type": "symlink", "mode": f"{mode:04o}", "target": os.readlink(path)})
        elif path.is_dir():
            rows.append({"path": relative, "type": "directory", "mode": f"{mode:04o}"})
        elif path.is_file():
            row = {"path": relative, "type": "file", "mode": f"{mode:04o}", "size": path.stat().st_size, "sha256": sha256(path)}
            elf = elf_contract(path)
            if elf is not None:
                row["elf"] = elf
            rows.append(row)
    return rows


def tree_digest(rows: list[dict]) -> str:
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def add_bytes(archive: tarfile.TarFile, name: str, payload: bytes, epoch: int, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = mode
    info.mtime = epoch
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    archive.addfile(info, io.BytesIO(payload))


def normalized_tarinfo(epoch: int):
    def filter_info(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        info.mtime = epoch
        return info
    return filter_info


def create(args: argparse.Namespace) -> None:
    recipe = yaml.safe_load(args.recipe.read_text())
    rows = inventory(args.root)
    manifest = {
        "schema": SCHEMA,
        "kind": "tideforge-staged-payload",
        "package": recipe["name"],
        "version": str(recipe["version"]),
        "release": int(recipe.get("release", 1)),
        "architecture": args.architecture,
        "build_contract": args.build_contract,
        "source_sha256": recipe["source"]["sha256"],
        "tree_sha256": tree_digest(rows),
        "files": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    with tarfile.open(args.output, "w", format=tarfile.PAX_FORMAT) as archive:
        add_bytes(archive, "manifest.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(), epoch)
        for path in sorted(args.root.rglob("*")):
            name = f"payload/{normalized_path(path.relative_to(args.root).as_posix())}"
            archive.add(path, arcname=name, recursive=False, filter=normalized_tarinfo(epoch))
    print(json.dumps({"intermediate": str(args.output), "tree_sha256": manifest["tree_sha256"], "files": len(rows)}, sort_keys=True))


def read_manifest(path: Path) -> dict:
    with tarfile.open(path, "r:*") as archive:
        member = archive.getmember("manifest.json")
        stream = archive.extractfile(member)
        if stream is None:
            raise SystemExit("intermediate has no readable manifest.json")
        manifest = json.load(stream)
    if manifest.get("schema") != SCHEMA or manifest.get("kind") != "tideforge-staged-payload":
        raise SystemExit("unsupported Tideforge intermediate")
    return manifest


def verify(args: argparse.Namespace) -> None:
    expected = read_manifest(args.intermediate)
    with tempfile.TemporaryDirectory(prefix="tideforge-intermediate-") as tmp:
        root = Path(tmp)
        with tarfile.open(args.intermediate, "r:*") as archive:
            for member in archive.getmembers():
                if member.name == "manifest.json":
                    continue
                normalized_path(member.name)
            archive.extractall(root, filter="data")
        actual_rows = inventory(root / "payload")
    actual = tree_digest(actual_rows)
    if actual != expected["tree_sha256"]:
        raise SystemExit(f"payload tree mismatch: expected {expected['tree_sha256']}, got {actual}")
    print(json.dumps({"package": expected["package"], "architecture": expected["architecture"], "tree_sha256": actual}, sort_keys=True))


def plan(args: argparse.Namespace) -> None:
    manifest = read_manifest(args.intermediate)
    recipe = yaml.safe_load(args.recipe.read_text())
    if manifest["package"] != recipe["name"] or manifest["version"] != str(recipe["version"]):
        raise SystemExit("recipe identity does not match intermediate")
    elf_files = [row for row in manifest["files"] if "elf" in row]
    target_deps = recipe.get("dependencies", {}).get("runtime", {}).get("targets", {}).get(args.target, [])
    print(json.dumps({
        "package": manifest["package"],
        "target": args.target,
        "architecture": manifest["architecture"],
        "payload_tree_sha256": manifest["tree_sha256"],
        "compile": False,
        "target_work": ["translate dependency names", "split files into native subpackages", "generate native metadata/scriptlets", "lint", "clean-install and smoke-test"],
        "declared_target_runtime_dependencies": target_deps,
        "elf_contracts": [{"path": row["path"], **row["elf"]} for row in elf_files],
    }, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create_parser = sub.add_parser("create")
    create_parser.add_argument("--recipe", type=Path, required=True)
    create_parser.add_argument("--root", type=Path, required=True)
    create_parser.add_argument("--architecture", required=True)
    create_parser.add_argument("--build-contract", required=True)
    create_parser.add_argument("--output", type=Path, required=True)
    create_parser.set_defaults(func=create)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("intermediate", type=Path)
    verify_parser.set_defaults(func=verify)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("intermediate", type=Path)
    plan_parser.add_argument("--recipe", type=Path, required=True)
    plan_parser.add_argument("--target", required=True)
    plan_parser.set_defaults(func=plan)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
