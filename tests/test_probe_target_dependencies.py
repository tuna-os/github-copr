"""Tests for Tideforge's disposable-container dependency probe."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("probe_target_dependencies", ROOT / "scripts" / "probe-target-dependencies.py")
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_probe_command_uses_a_disposable_podman_container() -> None:
    command = probe.podman_command("example.invalid/target:latest", "arch", ["rust", "pkgconf"])
    assert command[:4] == ["podman", "run", "--rm", "example.invalid/target:latest"]
    assert command[-2:] == ["rust", "pkgconf"]
    assert "pacman -Si" in command[6]


def test_native_dependencies_resolve_catalog_capabilities() -> None:
    recipe = {
        "dependencies": {
            "build": {"capabilities": ["rust"]},
            "runtime": {"capabilities": ["dbus"]},
        }
    }
    assert probe.native_dependencies(recipe, "ubuntu") == ["rustc", "cargo", "dbus"]
