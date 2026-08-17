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
# PEP-517 *backends* -- the things a pyproject.toml names in
# build-system.requires. python-build is deliberately not here: `build` is a
# frontend, a CLI that calls a backend, and no pyproject.toml requires it.
# Fedora's %pyproject_wheel does not use it either; pyproject_wheel.py calls
# the backend's build_wheel() directly. Listing it here was the premise behind
# putting it in the bootstrap tiers, and the premise was wrong.
BACKENDS = {
    "python-hatchling",
    "python-flit-core",
    "python-poetry-core",
    "python-editables",
    "python-trove-classifiers",
    "python-installer",
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
#   editables, installer, wheel         flit_core.buildapi
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

    bootstrap-* is named after no desktop, so any selection that goes by tier
    name skips it and every Python package in the run then builds against a
    backend that is not there.

    Asserted against the selection itself rather than against the text of the
    workflow step: the step used to hold the logic inline and now shells out to
    scripts/select-desktop-tiers.py, and the property is true of the answer
    either way.
    """
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location(
        "sdt", ROOT / "scripts" / "select-desktop-tiers.py"
    )
    sdt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sdt)

    manifest = yaml.safe_load(MANIFEST.read_text())
    report = json.loads((ROOT / "docs" / "hummingbird-desktop-gap.json").read_text())
    boot = [t["name"] for t in manifest["tiers"] if t["name"].startswith("bootstrap-")]
    assert boot, "the manifest has no bootstrap tiers to order first"

    for desktop in report["desktops"]:
        selected = sdt.select(manifest, report, desktop)
        assert selected[: len(boot)] == boot, (
            f"desktop={desktop} does not start with the bootstrap tiers, so the "
            "PEP-517 backends are missing when its Python packages build"
        )

    # And an explicit tier list still bypasses them, so one tier can be re-run.
    assert sdt.select(manifest, report, "gnome", requested=[boot[0]]) == [boot[0]]


def test_build_gets_pyproject_hooks_before_it_needs_it() -> None:
    """`build` requires pyproject_hooks at runtime, and nothing shipped it.

    Measured, not inferred -- run 31265856203, bootstrap-01, after flit-core
    had already built and been picked up:

        Handling flit-core >= 3.11 from build-system.requires
        Requirement satisfied: flit-core>=3.11
           (installed: flit-core 3.12.0)
        Handling pyproject_hooks from hook generated metadata: Requires-Dist (build)
        Requirement not satisfied: pyproject_hooks

    It is a plain Requires-Dist, so no bcond and no --nocheck reaches it: the
    only fix is to build it. docs/hummingbird-desktop-gap.md lists it among
    what `python-build` pulls, and the manifest then did not contain it --
    which is the gap the report exists to close, left open in the one tier
    every other tier waits on.
    """
    order = [t["name"] for t in tiers()]
    by_name = {t["name"]: names_in(t) for t in tiers()}

    def tier_of(pkg: str) -> int:
        return next(i for i, n in enumerate(order) if pkg in by_name[n])

    assert any("python-pyproject-hooks" in by_name[n] for n in order), (
        "python-pyproject-hooks is in no tier, so python-build cannot resolve "
        "its BuildRequires however the tiers are ordered"
    )
    # Under `membership: runtime` python-build is not built here at all -- it
    # is a build-time frontend no image ships, so it comes from the buildroot's
    # inherited Rawhide fallback with its pyproject_hooks Requires-Dist
    # resolved by dnf.  The ordering constraint above only binds when the
    # manifest does build it (a selfhost regeneration, or a future runtime
    # closure that pulls it in through an actual runtime dependency).
    if any("python-build" in by_name[n] for n in order):
        assert tier_of("python-build") > tier_of("python-pyproject-hooks"), (
            "python-build must build in a later tier than python-pyproject-hooks; "
            "packages inside a tier run concurrently, so sharing one is a race"
        )

def test_the_bootstrap_does_not_carry_a_pep517_frontend() -> None:
    """`build` is a frontend, not a backend, and nothing asked for it.

    python-build was put in the bootstrap tiers on the premise that Hummingbird
    ships no PEP-517 *backend*. That premise is right and `build` is not one of
    them: it is a CLI frontend, and Fedora's %pyproject_wheel does not use it --
    pyproject_wheel.py calls the backend's build_wheel() directly.

    It cannot be built here anyway. Fedora's spec hard-codes its optional
    extras, outside any bcond, so --without=tests --without=check does not
    reach them:

        pyproject_buildrequires.py --generate-extras ... -x virtualenv,uv
        Failed to resolve the transaction:
        Problem: package python3-uv-0.11.32-1.fc44.noarch requires
          uv = 0.11.32-1.fc44, but none of the providers can be installed

    (run 31266920109). uv is a Rust package that is not installable in this
    buildroot, so `build` costs the whole bootstrap and every tier behind it.

    Checked before removing, not after: `build` is in no desktop's closure, and
    across every tier built so far nothing emitted a requirement on it.

    If some package does turn out to need it, that will surface as a named
    unmet BuildRequires -- and the fix then is to make uv installable, not to
    re-add `build` on its own and rediscover this.
    """
    packages = {p for t in tiers() if t["name"].startswith("bootstrap-") for p in names_in(t)}
    assert "python-build" not in packages, (
        "python-build is back in the bootstrap tiers; it drags in an "
        "uninstallable uv and nothing was shown to need it -- see this "
        "test's docstring before re-adding it"
    )
