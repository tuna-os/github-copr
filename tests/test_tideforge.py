"""Tests for the single-recipe TunaOS package renderer."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tideforge", ROOT / "scripts" / "tideforge.py")
assert SPEC and SPEC.loader
tideforge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tideforge)


@pytest.fixture
def recipe() -> dict:
    return {
        "schema": 1,
        "name": "hello-tuna",
        "version": "1.2.3",
        "release": 1,
        "summary": "Hello Tuna",
        "description": "A test package.",
        "license": "Apache-2.0",
        "source": {"url": "https://example.com/hello-tuna-1.2.3.tar.gz", "sha256": "a" * 64},
        "build_system": "meson",
        "dependencies": {"build": {"common": ["meson"], "targets": {"el10": ["gcc"], "ubuntu": ["ninja-build"]}}},
        "files": {"common": ["usr/bin/hello-tuna"]},
        "targets": ["el10", "ubuntu", "debian"],
    }


def test_recipe_renders_el10_rpm(recipe: dict) -> None:
    tideforge.validate(recipe, "el10")
    rendered = tideforge.render(recipe, "el10")
    spec = rendered["hello-tuna.spec"]
    assert "BuildRequires: meson" in spec
    assert "BuildRequires: gcc" in spec
    assert "%meson_install" in spec


def test_recipe_renders_ubuntu_debian_metadata(recipe: dict) -> None:
    rendered = tideforge.render(recipe, "ubuntu")
    assert "Build-Depends: debhelper-compat (= 13), meson, ninja-build" in rendered["debian/control"]
    assert rendered["debian/hello-tuna.install"] == "usr/bin/hello-tuna\n"


def test_recipe_rejects_unknown_target(recipe: dict) -> None:
    recipe["targets"] = ["imaginary"]
    with pytest.raises(SystemExit):
        tideforge.validate(recipe)


def test_recipe_renders_subpackages(recipe: dict) -> None:
    recipe["outputs"] = {
        "rpm": {"subpackages": [{"name": "devel", "summary": "Headers", "files": ["usr/include/demo"]}]},
        "deb": {"packages": [{"name": "libdemo0", "files": ["usr/lib/libdemo.so.0"]}]},
    }
    rpm = tideforge.render(recipe, "el10")["hello-tuna.spec"]
    deb = tideforge.render(recipe, "ubuntu")
    assert "%package devel" in rpm
    assert "Package: libdemo0" in deb["debian/control"]
    assert "debian/libdemo0.install" in deb


def test_recipe_renders_arch_pkgbuild(recipe: dict) -> None:
    recipe["build_system"] = "cargo"
    recipe["targets"] = ["arch"]
    recipe["dependencies"]["build"]["targets"]["arch"] = ["pkgconf"]
    rendered = tideforge.render(recipe, "arch")["PKGBUILD"]
    assert "pkgname=hello-tuna" in rendered
    assert "cargo build --release --locked" in rendered
    assert "pkgconf" in rendered


def test_arch_pkgbuild_includes_runtime_dependencies(recipe: dict) -> None:
    recipe["targets"] = ["arch"]
    recipe["dependencies"]["runtime"] = {"targets": {"arch": ["glibc", "libinput>=1.0"]}}
    rendered = tideforge.render(recipe, "arch")["PKGBUILD"]
    assert "depends=('glibc' 'libinput>=1.0')" in rendered


def test_rpm_and_deb_preserve_runtime_dependencies(recipe: dict) -> None:
    recipe["dependencies"]["runtime"] = {"common": ["dbus"], "targets": {"el10": ["bluez"], "ubuntu": ["bluez"]}}
    rpm = tideforge.render(recipe, "el10")["hello-tuna.spec"]
    deb = tideforge.render(recipe, "ubuntu")["debian/control"]
    assert "Requires:       dbus" in rpm
    assert "Requires:       bluez" in rpm
    assert "Depends: ${shlibs:Depends}, ${misc:Depends}, dbus, bluez" in deb


def test_rpm_changelog_uses_a_valid_rpm_date(recipe: dict) -> None:
    spec = tideforge.render(recipe, "el10")["hello-tuna.spec"]
    assert "* Sat Jul 25 2026 TunaOS Package Factory" in spec


def test_go_rpm_disables_empty_automatic_debug_packages(recipe: dict) -> None:
    recipe["build_system"] = "go"
    spec = tideforge.render(recipe, "el10")["hello-tuna.spec"]
    assert spec.startswith("%global debug_package %{nil}\nName:")


def test_data_rpm_disables_empty_automatic_debug_packages(recipe: dict) -> None:
    recipe["build_system"] = "data"
    spec = tideforge.render(recipe, "el10")["hello-tuna.spec"]
    assert spec.startswith("%global debug_package %{nil}\nName:")


def test_recipe_renders_go_builds(recipe: dict) -> None:
    recipe["build_system"] = "go"
    rpm = tideforge.render(recipe, "el10")["hello-tuna.spec"]
    deb = tideforge.render(recipe, "debian")["debian/rules"]
    arch = tideforge.render(recipe, "arch")["PKGBUILD"]
    assert "go build -buildmode=pie" in rpm
    assert "go build -buildmode=pie" in deb
    assert "go build -buildmode=pie" in arch
    assert "debian/hello-tuna.install" not in tideforge.render(recipe, "debian")


def test_recipe_installs_reviewed_source_files(recipe: dict) -> None:
    recipe["install"] = {"files": [{"source": "demo.service", "destination": "usr/lib/systemd/system/demo.service"}]}
    assert "install -Dm0644 demo.service %{buildroot}/usr/lib/systemd/system/demo.service" in tideforge.render(recipe, "el10")["hello-tuna.spec"]
    assert "install -Dm0644 demo.service debian/hello-tuna/usr/lib/systemd/system/demo.service" in tideforge.render(recipe, "debian")["debian/rules"]
    assert "install -Dm0644 demo.service $pkgdir/usr/lib/systemd/system/demo.service" in tideforge.render(recipe, "arch")["PKGBUILD"]


def test_recipe_installs_reviewed_source_directories(recipe: dict) -> None:
    recipe["build_system"] = "data"
    recipe["install"] = {"directories": [{"source": "qml", "destination": "usr/share/demo"}]}
    assert "cp -a qml/. %{buildroot}/usr/share/demo/" in tideforge.render(recipe, "el10")["hello-tuna.spec"]
    assert "cp -a qml/. $pkgdir/usr/share/demo/" in tideforge.render(recipe, "arch")["PKGBUILD"]


def test_deb_rooted_source_directory_excludes_generated_debian_metadata(recipe: dict) -> None:
    recipe["build_system"] = "data"
    recipe["source"]["directory"] = "."
    recipe["install"] = {"directories": [{"source": ".", "destination": "usr/share/demo"}]}
    rules = tideforge.render(recipe, "ubuntu")["debian/rules"]
    assert '[ "$entry" = "./debian" ] && continue' in rules
    assert "debian/hello-tuna.install" not in tideforge.render(recipe, "ubuntu")


def test_rpm_rooted_release_archive_gets_a_safe_build_directory(recipe: dict) -> None:
    recipe["build_system"] = "data"
    recipe["source"]["directory"] = "."
    spec = tideforge.render(recipe, "el10")["hello-tuna.spec"]
    assert "%setup -q -c -n %{name}-%{version}" in spec
    assert "%autosetup -n ." not in spec


def test_go_recipe_uses_declared_module_and_binary(recipe: dict) -> None:
    recipe["build_system"] = "go"
    recipe["build"] = {"working_directory": "core", "go_package": "./cmd/demo", "binary": "demo"}
    assert "cd core\ngo build" in tideforge.render(recipe, "el10")["hello-tuna.spec"]
    assert "core/demo" in tideforge.render(recipe, "arch")["PKGBUILD"]


def test_cargo_recipe_uses_declared_workspace_and_binary(recipe: dict) -> None:
    recipe["build_system"] = "cargo"
    recipe["build"] = {"working_directory": "service", "cargo_package": "daemon", "binary": "demo-daemon"}
    rpm = tideforge.render(recipe, "el10")["hello-tuna.spec"]
    deb = tideforge.render(recipe, "debian")["debian/rules"]
    arch = tideforge.render(recipe, "arch")["PKGBUILD"]
    assert "cd service\ncargo build --release --locked --package daemon" in rpm
    assert "service/target/release/demo-daemon" in deb
    assert "cd service\n  cargo build --release --locked --package daemon" in arch


def test_dependency_capabilities_resolve_to_native_target_packages(recipe: dict) -> None:
    recipe["dependencies"]["build"] = {"capabilities": ["rust", "pkg-config"]}
    assert tideforge.target_dependencies(recipe, "el10") == ["rust", "cargo", "pkgconf-pkg-config"]
    assert tideforge.target_dependencies(recipe, "arch") == ["rust", "pkgconf"]


def test_unknown_dependency_capability_is_rejected(recipe: dict) -> None:
    recipe["dependencies"]["build"] = {"capabilities": ["imaginary-sdk"]}
    with pytest.raises(SystemExit):
        tideforge.validate(recipe)
