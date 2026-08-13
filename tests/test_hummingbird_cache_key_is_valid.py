"""A cache key that GitHub rejects skips the build and still reports success.

The Hummingbird desktop workflow keyed its mock-chroot cache on the selected
tier list. That list is comma-separated, and actions/cache refuses any key
containing a comma:

    ##[error]Key Validation Error: hummingbird-mock-<cfghash>-bootstrap-00,
    bootstrap-01,...,layer-23-<run_id> cannot contain commas.

It fired on every desktop of every run, in the same second the step started.
The damage was not a slow build from a cold cache. The cache step *fails*, so
`Build tiers` is skipped -- and the job carried on to sign and publish
whatever the R2 seed had already dropped into the local repo, then uploaded a
10 GB artifact. Runs 31687135147, 31688105850 and their predecessors reported
a published package repository having built exactly zero packages.

These tests build the key the workflow would build, from the real tier
selection, and check it against the constraints GitHub actually enforces.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-hummingbird-desktops.yml"
SELECTOR = ROOT / "scripts/select-desktop-tiers.py"
MANIFEST = ROOT / "build-order-hummingbird-desktops.yml"
GAP_REPORT = ROOT / "docs/hummingbird-desktop-gap.json"

DESKTOPS = ["gnome", "kde", "cosmic", "niri", "xfce"]

# GitHub's documented cache-key limit.
MAX_KEY_LEN = 512


@pytest.fixture(scope="module")
def build_steps():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    return workflow["jobs"]["build"]["steps"]


@pytest.fixture(scope="module")
def cache_steps(build_steps):
    steps = [s for s in build_steps if str(s.get("uses", "")).startswith("actions/cache")]
    assert steps, "no actions/cache step left in the build job"
    return steps


def _select(desktop):
    out = subprocess.run(
        [
            sys.executable,
            str(SELECTOR),
            "--manifest",
            str(MANIFEST),
            "--gap-report",
            str(GAP_REPORT),
            "--desktop",
            desktop,
            "--tiers",
            "",
            "--exclude-tiers",
            "",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


@pytest.mark.parametrize("desktop", DESKTOPS)
def test_the_tier_list_really_does_contain_commas(desktop):
    # The premise of every other test here. If the selector ever stops
    # emitting a comma-separated list this file is guarding a ghost, and the
    # failure below says so plainly rather than passing vacuously.
    assert "," in _select(desktop), (
        f"{desktop}'s tier list no longer contains commas -- re-check whether "
        "the cache key still needs a digest"
    )


def test_no_cache_key_interpolates_the_raw_tier_list(cache_steps):
    for step in cache_steps:
        for field in ("key", "restore-keys"):
            value = str(step["with"].get(field, ""))
            assert "outputs.list" not in value, (
                f"{step['name']!r} interpolates the comma-separated tier list "
                f"into {field}; actions/cache rejects the key outright and the "
                "build step is skipped"
            )


def test_the_selection_step_publishes_a_comma_free_digest(build_steps):
    tiers = next((s for s in build_steps if s.get("id") == "tiers"), None)
    assert tiers is not None, "the Select tiers step lost its id"
    assert "slug=" in tiers["run"], (
        "the Select tiers step must publish a digest of the selection for use "
        "in cache keys"
    )


@pytest.mark.parametrize("desktop", DESKTOPS)
def test_the_resolved_cache_key_is_one_github_accepts(cache_steps, desktop):
    # Substitute what the runner would substitute, then apply GitHub's rules.
    slug = subprocess.run(
        ["sha256sum"],
        input=_select(desktop),
        capture_output=True,
        text=True,
        check=True,
    ).stdout[:12]
    substitutions = {
        r"\$\{\{ matrix\.desktop \}\}": desktop,
        r"\$\{\{ hashFiles\('mock/hummingbird-ci\.cfg'\) \}\}": "f" * 64,
        r"\$\{\{ hashFiles\('build-order-hummingbird-desktops\.yml'\) \}\}": "e" * 64,
        r"\$\{\{ steps\.tiers\.outputs\.slug \}\}": slug,
        r"\$\{\{ github\.run_id \}\}": "31688105850",
    }

    for step in cache_steps:
        raw = [str(step["with"]["key"])]
        raw += str(step["with"].get("restore-keys", "")).splitlines()
        for key in (k.strip() for k in raw if k.strip()):
            for pattern, value in substitutions.items():
                key = re.sub(pattern, value, key)
            assert "${{" not in key, (
                f"{step['name']!r} still holds an unsubstituted expression "
                f"after {desktop}: {key!r} -- this test cannot vouch for it"
            )
            assert "," not in key, (
                f"{step['name']!r} resolves to a key with a comma for "
                f"{desktop}: {key!r}"
            )
            assert len(key) <= MAX_KEY_LEN, (
                f"{step['name']!r} resolves to a {len(key)}-character key for "
                f"{desktop}, over GitHub's {MAX_KEY_LEN} limit"
            )


def test_the_build_step_is_what_the_cache_step_guards(build_steps):
    # The reason a failed cache step was so expensive: `Build tiers` has no
    # if: of its own, so it inherits the job's failed state and is skipped,
    # while the publish steps that follow do not. Keep that adjacency visible
    # -- if a future edit puts the cache step somewhere else, this bug's blast
    # radius changes and the comment above should be re-read.
    names = [s.get("name", "") for s in build_steps]
    cache = next(i for i, n in enumerate(names) if n.startswith("Cache the mock chroot"))
    build = next(i for i, n in enumerate(names) if n == "Build tiers")
    assert cache < build, "the mock cache must be restored before the build runs"
