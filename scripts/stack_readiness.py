#!/usr/bin/env python3
"""Is this desktop buildable into a working stack yet?

## The question this answers, and who was answering it before

A repository full of packages is not a stack. The thing anyone actually wants
from "gnome 51 on hummingbird" is an image that boots into a usable session,
and tunaOS defines exactly that in `.github/green-criteria.yml`: a cell is
green only when it builds, ships the declared desktop, AND boots to its
contract target with `TUNAOS_DESKTOP_CONTRACT_OK` on the serial console.

Nothing on this side of the pipeline measured that. This module does, for the
half that is knowable here: **whether the packages a working session requires
are served at all.**

The failure it exists to catch is recorded in tunaOS's own
`build_scripts/checks/verify-desktop-experience.sh`:

    Measured on tunaOS run 32813037866 (2026-08-25): the image carried 410
    packages -- gnome-backgrounds and gnome-user-docs, no gnome-shell, no
    gdm, no mutter, no gtk4 -- and this check called it passed. The boot
    gate then failed 15 minutes later on a marker that could never be
    emitted, because the packages were dropped upstream
    (tunaos-packages#519).

hummingbird gets a deliberate waiver there (`IS_HUMMINGBIRD` turns every
requirement into a warning) so it can bootstrap against incomplete repos. That
policy is a human's to change. What it means in practice is that the image
build cannot tell you the repo is not ready — it builds an empty desktop, and
the boot gate discovers it a quarter of an hour later.

This side can answer it in seconds, from the served index, before anything is
dispatched.

## Why the count over the whole build order is the wrong number

Measured 2026-08-28 against the live hummingbird index:

    build order served                580/673   (86%)
    desktop contract served             3/10
    what the image installs            33/58

86% and 30%, of the same repo, on the same day. A loop optimising the first
number spends waves on vdirsyncer and hplip while gdm and gnome-shell are
absent, and every one of those waves moves 580/673 upward and moves the stack
not at all. So readiness is measured in ORDERED STAGES, and the first open one
is the only one that decides anything:

    contract  the desktop's `required_packages` -- what tunaOS's `desktop`
              criterion hard-fails on, and what the boot gate needs before a
              session can come up at all
    session   `install_packages` -- what tunaOS actually installs
              (manifests/desktops/<desktop>.yaml), the portals, keyring,
              pipewire units and gvfs backends that make a session usable
              rather than merely startable
    order     everything else the build order carries

Nothing here proves a desktop boots; only the gate does that. What it proves
is the negative, which is the half that was costing whole runs: when the
contract stage is open, the image CANNOT boot into a session, and building one
to find that out is fifteen minutes spent to learn something already known.

## The limit of a name

Readiness here is measured by NAME, and a name is necessary but not
sufficient. On 2026-08-28 the index served `gtk4` -- at 4.22.1, against a
gnome-shell that needs >= 4.23 -- so `gtk4` reads as satisfied while nothing
built against it can link. That is the same shape as the pango 1.57/1.58 wall
that cost the GNOME 51 bringup a whole night, and it is not a defect peculiar
to this module: tunaOS's own contract check says it "deliberately validates
names rather than image size or package count", and the gap engine resolves
requirements by name too.

So a closed `contract` stage says the packages EXIST, not that they satisfy
each other's version constraints. The tool that can already answer the second
question is scripts/simulate-buildroot-resolution.py, which evaluates
versioned and boolean dependencies against the real buildroot repo set; wiring
its verdict in as a fourth stage is the natural next increment, and until it
is, this module must not be read as claiming more than name-level presence.
"""
from __future__ import annotations

import dataclasses
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Ordered, and the order is the whole point: an earlier stage that is open
# makes every later one irrelevant to whether a stack can exist.
STAGE_ORDER = ("contract", "session", "order")

STAGE_WHY = {
    "contract": (
        "the desktop's required packages -- tunaOS's `desktop` criterion "
        "hard-fails without these, and the boot gate cannot emit its marker"
    ),
    "session": (
        "what the image installs: the portals, keyring, gvfs and session "
        "units that make a session usable rather than merely startable"
    ),
    "order": "the rest of the build order",
}


@dataclasses.dataclass(frozen=True)
class Stage:
    name: str
    wanted: tuple[str, ...]
    remaining: tuple[str, ...]

    @property
    def served(self) -> int:
        return len(self.wanted) - len(self.remaining)

    @property
    def closed(self) -> bool:
        return not self.remaining


def desktop_sets(roots_manifest: str, desktop: str) -> tuple[list[str], list[str]]:
    """(required_packages, install_packages-only) for one desktop.

    `install_packages` is returned with the contract names removed rather than
    as declared, so the stages partition the names instead of overlapping. An
    overlapping second stage would re-report the same missing gdm twice and
    make "session: 33/58" mean something different from "58 names".
    """
    catalog = yaml.safe_load((ROOT / roots_manifest).read_text(encoding="utf-8"))
    definition = (catalog.get("desktops") or {})[desktop]
    required = list(dict.fromkeys(definition.get("required_packages") or []))
    installed = [
        name
        for name in dict.fromkeys(definition.get("install_packages") or [])
        if name not in set(required)
    ]
    return required, installed


def stages(order_names: list[str], required: list[str], installed: list[str],
           served: set[str]) -> list[Stage]:
    """Partition every wanted name into an ordered stage, then score it."""
    claimed = set(required) | set(installed)
    tail = [name for name in order_names if name not in claimed]
    built: list[Stage] = []
    for name, wanted in (
        ("contract", required), ("session", installed), ("order", tail),
    ):
        built.append(Stage(
            name=name,
            wanted=tuple(wanted),
            remaining=tuple(n for n in wanted if n not in served),
        ))
    return built


def first_open(staged: list[Stage]) -> Stage | None:
    """The stage that decides. None when every stage is closed."""
    for stage in staged:
        if not stage.closed:
            return stage
    return None


def render(staged: list[Stage]) -> list[str]:
    lines = ["| stage | served | remaining | why it matters |",
             "| --- | --- | --- | --- |"]
    for stage in staged:
        lines.append(
            f"| `{stage.name}` | {stage.served}/{len(stage.wanted)} | "
            f"{len(stage.remaining)} | {STAGE_WHY[stage.name]} |"
        )
    open_stage = first_open(staged)
    lines.append("")
    if open_stage is None:
        lines.append(
            "Every package the stack needs is served. Whether it BOOTS is "
            "the gate's question, not this one."
        )
    else:
        shown = list(open_stage.remaining[:20])
        lines.append(
            f"Open stage: **{open_stage.name}** — "
            + ", ".join(f"`{n}`" for n in shown)
            + (" …" if len(open_stage.remaining) > 20 else "")
        )
    return lines
