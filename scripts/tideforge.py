#!/usr/bin/env python3
"""Tideforge: render one TunaOS recipe into native package metadata.

This deliberately owns the repetitive packaging boilerplate.  Recipes retain
small target-specific dependency overrides, because distro package names and
toolchain availability are real compatibility constraints.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "manifests" / "package-factory.yaml"
VALID_BUILD_SYSTEMS = {"meson", "autotools", "cmake", "cargo"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        fail(f"{path}: expected a mapping")
    return data


def load_targets() -> dict:
    return load_yaml(TARGETS)["targets"]


def target_dependencies(recipe: dict, target: str) -> list[str]:
    build = recipe.get("dependencies", {}).get("build", {})
    return list(build.get("common", [])) + list(build.get("targets", {}).get(target, []))


def validate(recipe: dict, target: str | None = None) -> None:
    if recipe.get("schema") != 1:
        fail("schema must be 1")
    for field in ("name", "version", "summary", "description", "license", "source", "build_system", "files", "targets"):
        if not recipe.get(field):
            fail(f"{field} is required")
    if not re.fullmatch(r"[a-z0-9][a-z0-9+._-]*", str(recipe["name"])):
        fail("name must be a lowercase package identifier")
    source = recipe["source"]
    if not source.get("url", "").startswith("https://"):
        fail("source.url must use HTTPS")
    if not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", ""))):
        fail("source.sha256 must be a 64-character lowercase SHA-256")
    if recipe["build_system"] not in VALID_BUILD_SYSTEMS:
        fail(f"build_system must be one of {sorted(VALID_BUILD_SYSTEMS)}")
    targets = load_targets()
    requested = recipe["targets"]
    if not isinstance(requested, list) or not requested:
        fail("targets must be a non-empty list")
    for item in requested:
        if item not in targets:
            fail(f"unknown target: {item}")
    if target and target not in requested:
        fail(f"recipe does not enable target: {target}")
    if not recipe["files"].get("common"):
        fail("files.common must list installed paths")


def rpm_build_lines(build_system: str) -> tuple[str, str]:
    if build_system == "meson":
        return "%meson\n%meson_build", "%meson_install"
    if build_system == "autotools":
        return "%configure\n%make_build", "%make_install"
    if build_system == "cargo":
        return "%cargo_build", "%cargo_install"
    return "%cmake\n%cmake_build", "%cmake_install"


def render_rpm(recipe: dict, target: str) -> dict[str, str]:
    build, install = rpm_build_lines(recipe["build_system"])
    requires = "\n".join(f"BuildRequires: {dep}" for dep in target_dependencies(recipe, target))
    rpm_output = recipe.get("outputs", {}).get("rpm", {})
    files = "\n".join(f"/{path.lstrip('/')}" for path in rpm_output.get("files", recipe["files"]["common"]))
    subpackage_definitions = "\n".join(
        f"%package {subpackage['name']}\nSummary: {subpackage['summary']}\n\n%description {subpackage['name']}\n{subpackage.get('description', subpackage['summary'])}\n"
        for subpackage in rpm_output.get("subpackages", [])
    )
    subpackage_files = "\n".join(
        f"%files {subpackage['name']}\n" + "\n".join(f"/{path.lstrip('/')}" for path in subpackage["files"]) + "\n"
        for subpackage in rpm_output.get("subpackages", [])
    )
    source_directory = recipe["source"].get("directory", f"%{{name}}-%{{version}}")
    spec = f"""Name:           {recipe['name']}
Version:        {recipe['version']}
Release:        {recipe.get('release', 1)}%{{?dist}}
Summary:        {recipe['summary']}
License:        {recipe['license']}
Source0:        {recipe['source']['url']}
{requires}

%description
{recipe['description']}

{subpackage_definitions}

%prep
%autosetup -n {source_directory}

%build
{build}

%install
{install}

%files
{files}

{subpackage_files}

%changelog
* Thu Jan 01 1970 TunaOS Package Factory <packages@tunaos.org> - {recipe['version']}-{recipe.get('release', 1)}
- Generated from package.yaml
"""
    return {f"{recipe['name']}.spec": spec}


def render_deb(recipe: dict, target: str) -> dict[str, str]:
    build_deps = ", ".join(target_dependencies(recipe, target))
    deb_output = recipe.get("outputs", {}).get("deb", {})
    binary_packages = deb_output.get("packages", [{"name": recipe["name"], "summary": recipe["summary"], "description": recipe["description"], "files": recipe["files"]["common"]}])
    package_stanzas = "\n".join(
        f"""Package: {package['name']}
Architecture: any
Depends: ${{shlibs:Depends}}, ${{misc:Depends}}
Description: {package.get('summary', recipe['summary'])}
 {package.get('description', recipe['description'])}
"""
        for package in binary_packages
    )
    control = f"""Source: {recipe['name']}
Section: misc
Priority: optional
Maintainer: TunaOS Package Factory <packages@tunaos.org>
Build-Depends: debhelper-compat (= 13){', ' if build_deps else ''}{build_deps}
Standards-Version: 4.7.0
Rules-Requires-Root: no

{package_stanzas}
"""
    buildsystem = {"meson": "meson", "autotools": "autoconf", "cmake": "cmake"}.get(recipe["build_system"])
    if recipe["build_system"] == "cargo":
        rules = f"#!/usr/bin/make -f\n\n%:\n\tdh $@\n\noverride_dh_auto_build:\n\tcargo build --release --locked\n\noverride_dh_auto_install:\n\tinstall -Dm0755 target/release/{recipe['name']} debian/{recipe['name']}/usr/bin/{recipe['name']}\n"
    else:
        rules = f"#!/usr/bin/make -f\n\n%:\n\tdh $@ --buildsystem={buildsystem}\n"
    changelog = f"{recipe['name']} ({recipe['version']}-{recipe.get('release', 1)}) {target}; urgency=medium\n\n  * Generated from package.yaml.\n\n -- TunaOS Package Factory <packages@tunaos.org>  Thu, 01 Jan 1970 00:00:00 +0000\n"
    rendered = {
        "debian/control": control,
        "debian/rules": rules,
        "debian/changelog": changelog,
        "debian/source/format": "3.0 (quilt)\n",
    }
    for package in binary_packages:
        rendered[f"debian/{package['name']}.install"] = "\n".join(package.get("files", recipe["files"]["common"])) + "\n"
    return rendered


def render(recipe: dict, target: str) -> dict[str, str]:
    target_data = load_targets()[target]
    if target_data["format"] == "rpm":
        return render_rpm(recipe, target)
    if target_data["format"] == "deb":
        return render_deb(recipe, target)
    fail(f"{target}: renderer for {target_data['format']} is scaffold-only")


def main() -> None:
    parser = argparse.ArgumentParser(prog="tideforge")
    commands = parser.add_subparsers(dest="command", required=True)
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("recipe", type=Path)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("recipe", type=Path)
    plan_parser.add_argument("--target", required=True)
    render_parser = commands.add_parser("render")
    render_parser.add_argument("recipe", type=Path)
    render_parser.add_argument("--target", required=True)
    render_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    recipe = load_yaml(args.recipe)
    target = getattr(args, "target", None)
    validate(recipe, target)
    if args.command == "validate":
        print(f"{args.recipe}: valid")
    elif args.command == "plan":
        print(json.dumps({"package": recipe["name"], "target": target, "build_dependencies": target_dependencies(recipe, target), "format": load_targets()[target]["format"]}, indent=2))
    else:
        for relative_path, content in render(recipe, target).items():
            destination = args.output / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content)
            if destination.name == "rules":
                destination.chmod(0o755)
        print(f"Rendered {recipe['name']} for {target} into {args.output}")


if __name__ == "__main__":
    main()
