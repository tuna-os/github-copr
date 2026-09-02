"""86% of the repo and 30% of the desktop are the same day, same index.

Measured against the live hummingbird index on 2026-08-28:

    build order served              580/673   (86%)
    desktop contract served           3/10
    what the image installs          33/58

A convergence that reports the first number keeps dispatching waves while gdm,
gnome-shell, gnome-session and nautilus are absent — and every one of those
waves moves 580/673 upward. The stack does not move at all, because tunaOS's
`desktop` criterion hard-fails without exactly those names and its boot Gate
waits out its timeout for a `TUNAOS_DESKTOP_CONTRACT_OK` marker that can never
be emitted.

That is not hypothetical. tunaOS's own build_scripts/checks/
verify-desktop-experience.sh records it:

    Measured on tunaOS run 32813037866 (2026-08-25): the image carried 410
    packages -- gnome-backgrounds and gnome-user-docs, no gnome-shell, no
    gdm, no mutter, no gtk4 -- and this check called it passed. The boot
    gate then failed 15 minutes later on a marker that could never be
    emitted, because the packages were dropped upstream
    (tunaos-packages#519).

So the objective is ordered stages, and these pin the ordering itself — the
property that makes the number mean "distance to a working stack" rather than
"distance to a full repository".
"""
from __future__ import annotations

import pathlib
import sys

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import stack_readiness as sr  # noqa: E402

# The set tunaOS's `desktop` criterion hard-fails on. Duplicated from this
# repo's own scripts/verify-gnome-desktop-experience.py deliberately: a test
# that imported the list it is checking would pass however that list changed.
TUNAOS_GNOME_CONTRACT = {
    "gdm", "gnome-keyring", "gnome-session", "gnome-shell", "gvfs", "mutter",
    "nautilus", "xdg-desktop-portal-gnome",
}


def test_the_contract_stage_covers_what_tunaos_hard_fails_on() -> None:
    """Our stage must not be narrower than the gate it is predicting.

    A contract stage that closed while gvfs was still missing would report
    `packages-ready`, green-light an image build, and the desktop criterion
    would fail on a name we never scored.
    """
    required, installed = sr.desktop_sets(
        "manifests/hummingbird-desktops.yaml", "gnome"
    )
    covered = set(required) | set(installed)
    missing = sorted(TUNAOS_GNOME_CONTRACT - covered)
    assert not missing, (
        "tunaOS hard-fails a GNOME image without these and no stage scores "
        f"them: {missing}"
    )


def test_the_stages_are_ordered_and_the_order_is_the_point() -> None:
    assert sr.STAGE_ORDER == ("contract", "session", "order")
    assert list(sr.STAGE_WHY) == list(sr.STAGE_ORDER)


def test_the_open_stage_is_the_earliest_one_with_work_left() -> None:
    staged = sr.stages(
        order_names=["tail-a", "tail-b"],
        required=["gdm", "gtk4"],
        installed=["gvfs"],
        served={"gtk4", "gvfs"},
    )
    assert sr.first_open(staged).name == "contract"
    # Closing it moves the objective on, even though `order` never changed.
    staged = sr.stages(
        order_names=["tail-a", "tail-b"],
        required=["gdm", "gtk4"],
        installed=["gvfs"],
        served={"gtk4", "gvfs", "gdm"},
    )
    assert sr.first_open(staged).name == "order"


def test_everything_served_means_no_open_stage() -> None:
    staged = sr.stages(["a"], ["b"], ["c"], {"a", "b", "c"})
    assert sr.first_open(staged) is None
    assert all(stage.closed for stage in staged)


def test_the_session_stage_never_repeats_the_contract() -> None:
    """Overlap would report the same missing gdm twice and inflate the count."""
    required, installed = sr.desktop_sets(
        "manifests/hummingbird-desktops.yaml", "gnome"
    )
    assert set(required) & set(installed) == set()


@pytest.mark.parametrize(
    "desktop",
    sorted(
        yaml.safe_load(
            (REPO / "manifests" / "hummingbird-desktops.yaml").read_text()
        )["desktops"]
    ),
)
def test_every_declared_desktop_has_a_contract_to_stage_by(desktop: str) -> None:
    """A desktop with no required_packages has no readiness question at all.

    It would report `packages-ready` from an empty contract stage on the first
    measurement — the loudest possible version of the 410-package image.
    """
    required, _ = sr.desktop_sets(
        "manifests/hummingbird-desktops.yaml", desktop
    )
    assert required, f"{desktop} declares no required_packages"


def test_the_rendered_table_leads_with_the_stage_that_decides() -> None:
    staged = sr.stages(["tail"], ["gdm"], ["gvfs"], set())
    text = "\n".join(sr.render(staged))
    assert text.index("`contract`") < text.index("`order`")
    assert "Open stage: **contract**" in text


def test_readiness_does_not_claim_the_desktop_boots() -> None:
    staged = sr.stages([], [], [], set())
    text = "\n".join(sr.render(staged))
    assert "BOOTS" in text and "gate" in text.lower(), (
        "an all-closed report that reads as success would send an image "
        "build off claiming a desktop nothing here measured"
    )


def test_the_name_level_limit_is_stated_where_it_is_relied_on() -> None:
    """`gtk4` served at 4.22.1 satisfies a name and not a >= 4.23 requirement.

    The pango 1.57/1.58 wall that cost the GNOME 51 bringup a night is exactly
    this shape. A module whose whole job is answering "is it ready" must say
    out loud what its answer does not cover, or the next reader takes a closed
    contract stage for a buildable one.
    """
    doc = (REPO / "scripts" / "stack_readiness.py").read_text(encoding="utf-8")
    assert "simulate-buildroot-resolution.py" in doc, (
        "the version-aware resolver is the tool that answers what a name "
        "cannot; the limit should point at it"
    )
    assert "4.22.1" in doc and "4.23" in doc
