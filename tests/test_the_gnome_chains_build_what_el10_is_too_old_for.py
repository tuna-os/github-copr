"""Where EL10 is below a GNOME version floor, the chain must build it itself.

Two packages in the gnome-50/gnome-51 chains ask for a dependency at a version
CentOS Stream 10 does not carry, and neither is optional -- both are hard
configure-time errors:

  gnome-settings-daemon 50.0   libnotify  >= 0.8.7   EL10 has 0.8.6
      meson.build:107:16: ERROR: Dependency lookup for libnotify with method
      'pkgconfig' failed: Invalid version, need 'libnotify' ['>= 0.8.7']
      found '0.8.6'.

  gnome-control-center 50.0    tecla      >= 47.0    EL10 has 45.0
      Dependency tecla found: NO. Found 45.0 but need: '>=47.0'
      ERROR: Subproject tecla is buildable: NO
      meson.build:199:10: ERROR: Automatic wrap-based subproject downloading
      is disabled

The second was invisible until the first was fixed: gnome-control-center was
one of three packages failing as pure cascade from libnotify, so its own
failure did not appear until libnotify built (run 32613066611).

Both were the SAME defect -- a recipe existed in the repository but was in no
build order, so it never built and never reached the buildroot:

  src/deps/libnotify   an artifact served from repo.tunaos.org that nothing
                       here could reproduce; given a spec, then an entry
  src/deps/tecla       a complete recipe, pinned at 50~rc, referenced by no
                       build order at all since it was added in March

A general rule was tried here and rejected on measurement: "a recipe exists
for pkgconfig(X), so the order must contain it" produces 91 violations
against the current tree, because most such recipes are overrides that only
some chains use while EL10 satisfies the rest (gtk4, cairo, pango...). The
recipe existing does not mean the order needs it. What makes these two
different is the measured version floor, and that is not visible offline --
so this file pins the two cases rather than inventing an invariant that is
not true.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# (build order, consumer, what it needs, the recipe that must precede it)
FLOORS = [
    ("build-order.yml", "src/gnome-50/gnome-settings-daemon", "libnotify", "src/deps/libnotify"),
    ("build-order-gnome51.yml", "src/gnome-51/gnome-settings-daemon", "libnotify", "src/deps/libnotify"),
    ("build-order.yml", "src/gnome-50/gnome-control-center", "tecla", "src/deps/tecla"),
    ("build-order-gnome51.yml", "src/gnome-51/gnome-control-center", "tecla", "src/deps/tecla"),
]


def tier_index(order: str) -> dict[str, int]:
    data = yaml.safe_load((ROOT / order).read_text(encoding="utf-8"))
    found: dict[str, int] = {}
    for i, tier in enumerate(data.get("tiers", [])):
        for pkg in tier.get("packages") or []:
            if pkg.get("path"):
                found[pkg["path"].rstrip("/")] = i
    return found


def test_each_floor_is_built_before_the_package_that_needs_it():
    problems = []
    for order, consumer, need, recipe in FLOORS:
        tiers = tier_index(order)
        if consumer not in tiers:
            problems.append(f"{order}: {consumer} absent")
            continue
        if recipe not in tiers:
            problems.append(f"{order}: {recipe} absent, but {consumer} needs {need}")
            continue
        if tiers[recipe] >= tiers[consumer]:
            problems.append(
                f"{order}: {recipe} at tier {tiers[recipe]} is not before "
                f"{consumer} at tier {tiers[consumer]}"
            )
    assert not problems, problems


def test_the_recipes_are_new_enough_to_clear_the_floor():
    """Building it is not enough if the version still sits under the floor."""
    versions = {}
    for recipe in ("src/deps/libnotify", "src/deps/tecla"):
        spec = next((ROOT / recipe).glob("*.spec"))
        text = spec.read_text(encoding="utf-8")
        versions[recipe] = re.search(r"^Version:\s*(\S+)", text, re.M).group(1)

    # EL10 ships libnotify 0.8.6; gnome-settings-daemon needs >= 0.8.7.
    assert versions["src/deps/libnotify"] == "0.8.7", versions

    # EL10 ships tecla 45.0; gnome-control-center needs >= 47.0. A `~`
    # pre-release would sort BELOW the plain version in rpm, so a release
    # candidate is not an acceptable answer here.
    tecla = versions["src/deps/tecla"]
    assert "~" not in tecla, f"tecla pinned to a pre-release: {tecla}"
    assert int(tecla.split(".")[0]) >= 47, tecla


def test_a_recipe_in_no_build_order_is_what_broke_both():
    """The failure mode, stated as a check: these two paths must appear in
    the gnome orders. Before this fix src/deps/tecla appeared in neither,
    which is why gnome-control-center resolved against EL10's 45.0."""
    for order in ("build-order.yml", "build-order-gnome51.yml"):
        tiers = tier_index(order)
        assert "src/deps/tecla" in tiers, order
        assert "src/deps/libnotify" in tiers, order
