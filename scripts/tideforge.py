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
VALID_BUILD_SYSTEMS = {"meson", "autotools", "cmake", "cargo", "go", "data"}


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


def load_dependency_catalog() -> dict:
    return load_yaml(TARGETS).get("dependency_catalog", {})


def resolve_capabilities(capabilities: list[str], target: str) -> list[str]:
    catalog = load_dependency_catalog()
    packages: list[str] = []
    for capability in capabilities:
        if capability not in catalog:
            fail(f"unknown dependency capability: {capability}")
        target_packages = catalog[capability].get(target)
        if not isinstance(target_packages, list) or not target_packages:
            fail(f"dependency capability {capability} has no mapping for {target}")
        packages.extend(target_packages)
    return packages


def target_dependencies(recipe: dict, target: str) -> list[str]:
    build = recipe.get("dependencies", {}).get("build", {})
    return list(build.get("common", [])) + resolve_capabilities(list(build.get("capabilities", [])), target) + list(build.get("targets", {}).get(target, []))


def target_runtime_dependencies(recipe: dict, target: str) -> list[str]:
    runtime = recipe.get("dependencies", {}).get("runtime", {})
    return list(runtime.get("common", [])) + resolve_capabilities(list(runtime.get("capabilities", [])), target) + list(runtime.get("targets", {}).get(target, []))


def install_commands(recipe: dict, destination_root: str) -> str:
    commands: list[str] = []
    for item in recipe.get("install", {}).get("files", []):
        commands.append(f"install -Dm{item.get('mode', '0644')} {item['source']} {destination_root}/{item['destination']}")
    return "\n".join(commands)


def install_directories(recipe: dict, destination_root: str, *, exclude_generated_debian: bool = False) -> str:
    commands: list[str] = []
    for item in recipe.get("install", {}).get("directories", []):
        commands.append(f"install -d {destination_root}/{item['destination']}")
        # Debian's package staging directory lives below the unpacked source.
        # A release archive rooted at `.` would otherwise recursively copy that
        # generated directory into its own destination during dh_auto_install.
        if exclude_generated_debian and item["source"] == ".":
            commands.append(
                f'for entry in ./* ./.??*; do [ "$$entry" = "./debian" ] && continue; '
                f'[ -e "$$entry" ] || continue; cp -a "$$entry" {destination_root}/{item["destination"]}/; done'
            )
        else:
            commands.append(f"cp -a {item['source']}/. {destination_root}/{item['destination']}/")
    return "\n".join(commands)


def build_option(recipe: dict, option: str, default: str) -> str:
    return str(recipe.get("build", {}).get(option, default))


def cargo_options(recipe: dict) -> tuple[str, str, str]:
    """Return the Cargo workspace directory, package selector, and binary."""
    return (
        build_option(recipe, "working_directory", "."),
        build_option(recipe, "cargo_package", ""),
        build_option(recipe, "binary", recipe["name"]),
    )


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
    for dependency_kind in ("build", "runtime"):
        dependency_data = recipe.get("dependencies", {}).get(dependency_kind, {})
        capabilities = dependency_data.get("capabilities", [])
        if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):
            fail(f"dependencies.{dependency_kind}.capabilities must be a list of capability names")
        for requested_target in requested:
            resolve_capabilities(capabilities, requested_target)
    if not recipe["files"].get("common"):
        fail("files.common must list installed paths")
    for item in recipe.get("install", {}).get("files", []) + recipe.get("install", {}).get("directories", []):
        if not isinstance(item, dict) or not isinstance(item.get("source"), str) or not isinstance(item.get("destination"), str):
            fail("install.files entries need source and destination")
        if item["source"].startswith("/") or item["destination"].startswith("/") or ".." in Path(item["source"]).parts or ".." in Path(item["destination"]).parts:
            fail("install.files paths must stay relative")


def rpm_build_lines(build_system: str) -> tuple[str, str]:
    if build_system == "meson":
        return "%meson\n%meson_build", "%meson_install"
    if build_system == "autotools":
        return "%configure\n%make_build", "%make_install"
    if build_system == "cargo":
        return "%cargo_build", "%cargo_install"
    if build_system == "go":
        return "go build -buildmode=pie -trimpath -mod=readonly -o %{name} .", "install -Dm0755 %{name} %{buildroot}%{_bindir}/%{name}"
    if build_system == "data":
        return ":", ":"
    return "%cmake\n%cmake_build", "%cmake_install"


def render_rpm(recipe: dict, target: str) -> dict[str, str]:
    build, install = rpm_build_lines(recipe["build_system"])
    if recipe["build_system"] == "go":
        workdir = build_option(recipe, "working_directory", ".")
        binary = build_option(recipe, "binary", recipe["name"])
        package = build_option(recipe, "go_package", ".")
        build = f"cd {workdir}\ngo build -buildmode=pie -trimpath -mod=readonly -o {binary} {package}"
        install = f"install -Dm0755 {workdir}/{binary} %{{buildroot}}%{{_bindir}}/{binary}"
    elif recipe["build_system"] == "cargo":
        workdir, cargo_package, binary = cargo_options(recipe)
        selector = f" --package {cargo_package}" if cargo_package else ""
        build = f"cd {workdir}\nCARGO_PROFILE_RELEASE_DEBUG=1 cargo build --release --locked{selector}"
        install = f"install -Dm0755 {workdir}/target/release/{binary} %{{buildroot}}%{{_bindir}}/{binary}"
    requires = "\n".join(f"BuildRequires: {dep}" for dep in target_dependencies(recipe, target))
    runtime_requires = "\n".join(f"Requires:       {dep}" for dep in target_runtime_dependencies(recipe, target))
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
    # Release assets sometimes contain files directly at archive root rather
    # than a conventional name-version directory.  RPM's %autosetup cannot
    # safely use `-n .` (it attempts `rm -rf .`).  Create an isolated build
    # directory before unpacking such sources instead.
    prep = (
        "%setup -q -c -n %{name}-%{version}"
        if source_directory == "."
        else f"%autosetup -n {source_directory}"
    )
    extra_install = "\n".join(filter(None, [install_commands(recipe, "%{buildroot}"), install_directories(recipe, "%{buildroot}")]))
    # Tideforge's Go and data renderers do not produce RPM-compatible
    # debug-source payloads. Cargo builds retain debuginfo so native RPM debug
    # packages can be generated normally.
    rpm_preamble = ""
    if recipe["build_system"] in {"go", "data"}:
        rpm_preamble = "%global debug_package %{nil}\n"
    spec = f"""{rpm_preamble}Name:           {recipe['name']}
Version:        {recipe['version']}
Release:        {recipe.get('release', 1)}%{{?dist}}
Summary:        {recipe['summary']}
License:        {recipe['license']}
Source0:        {recipe['source']['url']}
{requires}
{runtime_requires}

%description
{recipe['description']}

{subpackage_definitions}

%prep
{prep}

%build
{build}

%install
{install}
{extra_install}

%files
{files}

{subpackage_files}

%changelog
* Sat Jul 25 2026 TunaOS Package Factory <packages@tunaos.org> - {recipe['version']}-{recipe.get('release', 1)}
- Generated from package.yaml
"""
    return {f"{recipe['name']}.spec": spec}


def render_deb(recipe: dict, target: str) -> dict[str, str]:
    build_deps = ", ".join(target_dependencies(recipe, target))
    deb_output = recipe.get("outputs", {}).get("deb", {})
    binary_packages = deb_output.get("packages", [{"name": recipe["name"], "summary": recipe["summary"], "description": recipe["description"], "files": recipe["files"]["common"]}])
    recipe_runtime_dependencies = target_runtime_dependencies(recipe, target)
    package_stanzas = "\n".join(
        f"""Package: {package['name']}
Architecture: any
Depends: {', '.join(['${shlibs:Depends}', '${misc:Depends}', *recipe_runtime_dependencies, *package.get('depends', [])])}
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
        workdir, cargo_package, binary = cargo_options(recipe)
        selector = f" --package {cargo_package}" if cargo_package else ""
        rules = f"#!/usr/bin/make -f\n\n%:\n\tdh $@\n\noverride_dh_auto_build:\n\tcd {workdir} && CARGO_PROFILE_RELEASE_DEBUG=1 cargo build --release --locked{selector}\n\noverride_dh_auto_install:\n\tinstall -Dm0755 {workdir}/target/release/{binary} debian/{recipe['name']}/usr/bin/{binary}\n"
    elif recipe["build_system"] == "go":
        workdir = build_option(recipe, "working_directory", ".")
        binary = build_option(recipe, "binary", recipe["name"])
        package = build_option(recipe, "go_package", ".")
        rules = f"#!/usr/bin/make -f\n\n%:\n\tdh $@\n\noverride_dh_auto_build:\n\tcd {workdir} && go build -buildmode=pie -trimpath -mod=readonly -o {binary} {package}\n\noverride_dh_auto_install:\n\tinstall -Dm0755 {workdir}/{binary} debian/{recipe['name']}/usr/bin/{binary}\n"
    elif recipe["build_system"] == "data":
        rules = "#!/usr/bin/make -f\n\n%:\n\tdh $@\n\noverride_dh_auto_build:\n\t:\n\noverride_dh_auto_install:\n\t:\n"
    else:
        rules = f"#!/usr/bin/make -f\n\n%:\n\tdh $@ --buildsystem={buildsystem}\n"
    extra_install = "\n".join(filter(None, [install_commands(recipe, f"debian/{recipe['name']}"), install_directories(recipe, f"debian/{recipe['name']}", exclude_generated_debian=True)]))
    if extra_install:
        rules = rules.rstrip() + "\n\t" + extra_install.replace("\n", "\n\t") + "\n"
    changelog = f"{recipe['name']} ({recipe['version']}-{recipe.get('release', 1)}) {target}; urgency=medium\n\n  * Generated from package.yaml.\n\n -- TunaOS Package Factory <packages@tunaos.org>  Thu, 01 Jan 1970 00:00:00 +0000\n"
    rendered = {
        "debian/control": control,
        "debian/rules": rules,
        "debian/changelog": changelog,
        "debian/source/format": "3.0 (quilt)\n",
    }
    # Tideforge's Go, Cargo, and data renderers install directly into
    # debian/<binary-package>.  A .install file would make dh_install search
    # debian/tmp for those same files and fail the package build.  Native
    # build-system packages retain .install metadata for dh_auto_install.
    direct_install = recipe["build_system"] in {"cargo", "go", "data"} or bool(recipe.get("install"))
    if not direct_install:
        for package in binary_packages:
            rendered[f"debian/{package['name']}.install"] = "\n".join(package.get("files", recipe["files"]["common"])) + "\n"
    return rendered


def render_pkgbuild(recipe: dict, target: str) -> dict[str, str]:
    """Render an Arch PKGBUILD for the straightforward single-binary case.

    Complex split packages and packaging hooks stay native until the recipe
    schema can model them without hiding Arch-specific behaviour.
    """
    source_directory = recipe["source"].get("directory", f"{recipe['name']}-{recipe['version']}")
    makedepends = " ".join(f"'{dependency}'" for dependency in target_dependencies(recipe, target))
    depends = " ".join(f"'{dependency}'" for dependency in target_runtime_dependencies(recipe, target))
    source_name = f"{recipe['name']}-{recipe['version']}.tar.gz"
    source = recipe["source"]["url"]
    if recipe["build_system"] == "cargo":
        workdir, cargo_package, binary = cargo_options(recipe)
        selector = f" --package {cargo_package}" if cargo_package else ""
        build = f"cd {workdir}\n  CARGO_PROFILE_RELEASE_DEBUG=1 cargo build --release --locked{selector}"
        install = f"install -Dm0755 {workdir}/target/release/{binary} \"$pkgdir/usr/bin/{binary}\""
    elif recipe["build_system"] == "go":
        workdir = build_option(recipe, "working_directory", ".")
        binary = build_option(recipe, "binary", recipe["name"])
        package = build_option(recipe, "go_package", ".")
        build = f"cd {workdir}\n  go build -buildmode=pie -trimpath -mod=readonly -o {binary} {package}"
        install = f"install -Dm0755 {workdir}/{binary} \"$pkgdir/usr/bin/{binary}\""
    elif recipe["build_system"] == "data":
        build = ":"
        install = ":"
    elif recipe["build_system"] == "meson":
        build = "arch-meson build\n  meson compile -C build"
        install = "DESTDIR=\"$pkgdir\" meson install -C build"
    elif recipe["build_system"] == "autotools":
        build = "./configure --prefix=/usr\n  make"
        install = "make DESTDIR=\"$pkgdir\" install"
    else:
        build = "cmake -B build -S . -DCMAKE_INSTALL_PREFIX=/usr\n  cmake --build build"
        install = "DESTDIR=\"$pkgdir\" cmake --install build"
    extra_install = "\n".join(filter(None, [install_commands(recipe, "$pkgdir"), install_directories(recipe, "$pkgdir")]))
    if extra_install:
        install = f"{install}\n  {extra_install.replace(chr(10), chr(10) + '  ')}"
    pkgbuild = f"""# Generated by Tideforge; target-specific dependencies remain in package.yaml.
pkgname={recipe['name']}
pkgver={recipe['version']}
pkgrel={recipe.get('release', 1)}
pkgdesc={recipe['summary']!r}
arch=('x86_64' 'aarch64')
url={source!r}
license=({recipe['license']!r})
makedepends=({makedepends})
depends=({depends})
source=('{source_name}::{source}')
sha256sums=('{recipe['source']['sha256']}')

build() {{
  cd \"$srcdir/{source_directory}\"
  {build}
}}

package() {{
  cd \"$srcdir/{source_directory}\"
  {install}
}}
"""
    return {"PKGBUILD": pkgbuild}


def render(recipe: dict, target: str) -> dict[str, str]:
    target_data = load_targets()[target]
    if target_data["format"] == "rpm":
        return render_rpm(recipe, target)
    if target_data["format"] == "deb":
        return render_deb(recipe, target)
    if target_data["format"] == "pkg.tar.zst":
        return render_pkgbuild(recipe, target)
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
