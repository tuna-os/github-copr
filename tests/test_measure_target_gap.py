"""RFC 011 Phase 1: the generic gap command resolves target inputs centrally."""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "gap", ROOT / "scripts" / "measure-hummingbird-gap.py"
)
gap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gap)


def factory() -> dict:
    return yaml.safe_load(
        (ROOT / "manifests" / "package-factory.yaml").read_text(encoding="utf-8")
    )


def test_hummingbird_gap_contract_is_complete() -> None:
    measurement = gap.target_measurement(factory(), "hummingbird")
    assert measurement["roots_manifest"] == "manifests/hummingbird-desktops.yaml"
    assert measurement["target_index"].startswith("https://")
    assert measurement["reference_index"].startswith("https://")


def test_fedora_xfce_gap_contract_is_complete() -> None:
    measurement = gap.target_measurement(factory(), "fedora")
    assert measurement["roots_manifest"] == "manifests/xfce-fedora.yaml"
    assert "releases/44" in measurement["target_index"]
    assert "rawhide" in measurement["reference_index"]


def test_target_without_gap_contract_is_not_silently_measured() -> None:
    with pytest.raises(SystemExit, match="no gap_measurement contract"):
        gap.target_measurement(factory(), "el10")


def test_generic_entrypoint_is_checked_in() -> None:
    entrypoint = ROOT / "scripts" / "measure-target-gap.py"
    body = entrypoint.read_text(encoding="utf-8")
    assert "measure-hummingbird-gap.py" in body
    assert "_engine.main()" in body
    assert "requires --target" in body
