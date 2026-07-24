#!/usr/bin/env python3
"""Import Fedora dist-git RPM packaging into src/hummingbird.

Only packaging inputs are copied (specs, patches, source declarations and
auxiliary build files); the dist-git repository itself is never nested in this
repository.  The result is reviewable and can be built by build-chain.sh.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import tempfile

import yaml


def fedora_packages(catalog: pathlib.Path) -> list[str]:
    data = yaml.safe_load(catalog.read_text())
    result: list[str] = []
    for desktop in data["desktops"].values():
        for source in desktop["sources"]:
            package = source.get("fedora_distgit")
            if package and package not in result:
                result.append(package)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=pathlib.Path)
    parser.add_argument("--branch", default="rawhide")
    parser.add_argument("--package", action="append", dest="packages")
    parser.add_argument("--dest", type=pathlib.Path, default=pathlib.Path("src/hummingbird"))
    args = parser.parse_args()

    packages = args.packages or fedora_packages(args.catalog)
    destination = args.dest.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tunaos-distgit-") as temp:
        tempdir = pathlib.Path(temp)
        for package in packages:
            target = destination / package
            if target.exists():
                print(f"Skipping {package}: {target} already exists")
                continue
            checkout = tempdir / package
            url = f"https://src.fedoraproject.org/rpms/{package}.git"
            subprocess.run(["git", "clone", "--depth", "1", "--branch", args.branch, url, str(checkout)], check=True)
            target.mkdir()
            for source in checkout.iterdir():
                if source.name == ".git":
                    continue
                shutil.copytree(source, target / source.name) if source.is_dir() else shutil.copy2(source, target / source.name)
            print(f"Imported {package} from {args.branch}")


if __name__ == "__main__":
    main()
