"""The Fedora shadow result must not silently replace the executed order."""
from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/rfc011/fedora-xfce-shadow-gap.json"
CANDIDATE = ROOT / "docs/rfc011/build-order-xfce-fedora.candidate.yml"
DISPOSITION = ROOT / "docs/rfc011/fedora-xfce-shadow-measurement.md"
EXECUTED = ROOT / "build-order-xfce-fedora.yml"


def names(order: Path) -> list[str]:
    data = yaml.safe_load(order.read_text(encoding="utf-8"))
    return [
        package.get("distgit") or package["path"].rsplit("/", 1)[-1]
        for tier in data["tiers"]
        for package in tier["packages"]
    ]


def test_shadow_candidate_has_a_reviewed_disposition_for_every_delta() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    xfce = report["desktops"]["xfce"]
    text = DISPOSITION.read_text(encoding="utf-8")

    assert names(EXECUTED) == ["xfconf", "libxfce4ui", "xfwl4"]
    assert names(CANDIDATE) == []
    assert xfce["roots_already_in_target"] == ["libxfce4ui", "xfconf"]
    assert xfce["roots_absent_from_reference"] == ["xfwl4"]
    assert "required Fedora 44 version-floor upgrade" in text
    assert "upstream Rawhide change not valid for the Fedora 44 target" in text
