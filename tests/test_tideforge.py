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
