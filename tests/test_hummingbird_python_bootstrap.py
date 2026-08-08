"""Hummingbird has no PEP-517 build backends, so we must build them first.

Measured against the target's own primary.xml (3384 distinct package names):
Hummingbird ships `pyproject-rpm-macros`, `python3-devel`, `python3-setuptools`,
`python3-packaging`, `python3-pytest`, `python3-pathspec` and `python3-pluggy`
-- and NOT ONE build backend.  No hatchling, flit-core, poetry-core, wheel,
installer, build, editables or trove-classifiers.

`%pyproject_buildrequires` therefore emits e.g. `python3-hatchling`, dnf finds
it only in Rawhide, and Rawhide's build is for Python 3.15 while Hummingbird is
on 3.14 -- `docs/hummingbird-desktop-gap.md` Finding 3 records the split as
"different libpython3.x.so.1.0".  The 3.15 backend then demands
`python3.15dist(packaging)` while the installed packaging provides
`python3.14dist(...)`, and the transaction cannot resolve:

    cannot install both python3-packaging-26.2-4.fc45.noarch from fedora and
    python3-packaging-26.2-4.1.hum1.noarch from @System

All 8 python-* packages of tier niri-00 failed exactly this way in runs
31231968581, 31242725235 and 31248093019 -- the same 8, the same error, three
times.  It is not specific to them: every Python package in the 670-package
desktop gap builds through a PEP-517 backend.

Why the gap analysis missed it: the closure is over runtime `Requires:`, and a
build backend appears only in `BuildRequires`.  It was never a candidate.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "build-order-hummingbird-desktops.yml"
WORKFLOW = ROOT / ".github/workflows/build-hummingbird-desktops.yml"

# Every backend Hummingbird lacks that pyproject-rpm-macros can name.
BACKENDS = {
    "python-hatchling",
    "python-flit-core",
    "python-poetry-core",
    "python-editables",
    "python-trove-classifiers",
    "python-installer",
    "python-build",
    "python-wheel",
}


def tiers() -> list[dict]:
    return yaml.safe_load(MANIFEST.read_text())["tiers"]


def names_in(tier: dict) -> set[str]:
    return {Path(p["path"]).name for p in tier["packages"]}


def test_every_missing_backend_is_scheduled() -> None:
    scheduled = set()
    for t in tiers():
        scheduled |= names_in(t)
    missing = BACKENDS - scheduled
    assert not missing, (
        f"these build backends are absent from Hummingbird AND from the build "
        f"order, so anything needing them resolves a Python 3.15 build out of "
        f"Rawhide and fails to install: {sorted(missing)}"
    )


def test_backends_are_built_before_the_desktops() -> None:
    """A backend built after the package that needs it is no use."""
    order = [t["name"] for t in tiers()]
    by_name = {t["name"]: names_in(t) for t in tiers()}
    first_desktop = next(
        (i for i, n in enumerate(order) if not n.startswith("bootstrap-")), None
    )
    assert first_desktop is not None, "manifest has no desktop tiers at all"
    for backend in BACKENDS:
        at = next(
            (i for i, n in enumerate(order) if backend in by_name[n]), None
        )
        assert at is not None, f"{backend} is not scheduled"
        assert at < first_desktop, (
            f"{backend} is built in tier '{order[at]}', after the desktop tiers "
            f"start at '{order[first_desktop]}'"
        )


# Each package's declared PEP-517 backend, read out of its own sdist
# pyproject.toml rather than guessed:
#
#   flit-core, poetry-core, hatchling   self-hosting
#   trove-classifiers                   setuptools.build_meta  (in Hummingbird)
#   editables, installer, build, wheel  flit_core.buildapi
#   hatch-vcs, hatch-fancy-pypi-readme  hatchling.build
#
# A backend must be BUILT before anything that builds with it, and packages
# inside one tier run concurrently -- so "earlier tier", not "earlier in the
# list". The first cut of this file had editables and installer sharing a tier
# with flit-core, and hatchling sharing one with the trove-classifiers and
# editables it needs; both would have failed on the first dispatch.
BACKEND_OF = {
    "python-editables": "python-flit-core",
    "python-installer": "python-flit-core",
    "python-build": "python-flit-core",
    "python-wheel": "python-flit-core",
    "python-hatch-vcs": "python-hatchling",
    "python-hatch-fancy-pypi-readme": "python-hatchling",
}


def test_each_backend_is_built_before_its_dependents() -> None:
    order = [t["name"] for t in tiers()]
    by_name = {t["name"]: names_in(t) for t in tiers()}

    def tier_of(pkg: str) -> int:
        return next(i for i, n in enumerate(order) if pkg in by_name[n])

    for pkg, backend in BACKEND_OF.items():
        assert tier_of(pkg) > tier_of(backend), (
            f"{pkg} declares build-backend {backend!r} but is in tier "
            f"'{order[tier_of(pkg)]}', not after '{order[tier_of(backend)]}'. "
            "Packages inside a tier run concurrently, so sharing one is the "
            "same as building it first."
        )


def test_hatchling_follows_its_own_runtime_deps() -> None:
    """%pyproject_buildrequires emits runtime deps too, not just the backend."""
    order = [t["name"] for t in tiers()]
    by_name = {t["name"]: names_in(t) for t in tiers()}

    def tier_of(pkg: str) -> int:
        return next(i for i, n in enumerate(order) if pkg in by_name[n])

    for dep in ("python-editables", "python-trove-classifiers"):
        assert tier_of("python-hatchling") > tier_of(dep), (
            f"hatchling requires {dep} at runtime, so it must build in a later "
            "tier than it"
        )


def test_the_workflow_runs_the_bootstrap_tiers_first() -> None:
    """Selecting `desktop: gnome` must still get the backends.

    The tier filter is a name prefix, so bootstrap-* matches no desktop and
    would otherwise be skipped by every ordinary dispatch.
    """
    select = next(
        s
        for s in yaml.safe_load(WORKFLOW.read_text())["jobs"]["build"]["steps"]
        if s.get("name") == "Select tiers"
    )["run"]
    assert 'startswith("bootstrap-")' in select, (
        "the Select tiers step does not single out the bootstrap tiers, so "
        "`desktop: gnome` selects only gnome-* and builds no backends"
    )
    assert "boot + [" in select, "bootstrap tiers are not prepended to the selection"
