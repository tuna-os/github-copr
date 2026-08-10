"""The desktop builds must use the caches the rest of Tideforge uses.

build-chain.sh has honoured MOCK_CACHE_DIR and RPM_SOURCES_CACHE for a long
time. The Hummingbird workflow set neither, so every dispatch re-resolved the
same buildroot for every package and re-downloaded every upstream tarball --
on a tier of a hundred-odd packages, and a desktop of over a thousand.

RPM_SOURCES_CACHE was additionally only honoured on the mock backend. The
desktop builds run the podman backend, so even setting it would have done
nothing until that path learned it too.
"""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github/workflows/build-hummingbird-desktops.yml"
BUILD_CHAIN = REPO / "scripts/build-chain.sh"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def build_step() -> dict:
    steps = workflow()["jobs"]["build"]["steps"]
    return next(s for s in steps if s.get("name") == "Build tiers")


def test_the_build_step_sets_both_cache_variables():
    env = build_step().get("env", {})
    assert "MOCK_CACHE_DIR" in env, "the chroot and its dnf downloads are not cached"
    assert "RPM_SOURCES_CACHE" in env, "upstream tarballs are not cached"


def resolved(path: str) -> str:
    """What an actions/cache `path:` actually names.

    A relative path is taken from the workspace; an absolute one is itself.
    The chroot cache is deliberately absolute and outside the checkout --
    keepcache=1 fills it with unsigned third-party RPMs -- so this has to
    compare the directory the two sides mean, not the string they spell.
    """
    if path.startswith("/") or path.startswith("${{"):
        return path
    return "${{ github.workspace }}/" + path


def test_both_cache_paths_are_actually_cached_across_runs():
    """Setting the variable without an actions/cache only moves the directory."""
    steps = workflow()["jobs"]["build"]["steps"]
    cached = {
        resolved(s["with"]["path"])
        for s in steps
        if str(s.get("uses", "")).startswith("actions/cache") and s.get("with", {}).get("path")
    }
    env = build_step()["env"]
    for var in ("MOCK_CACHE_DIR", "RPM_SOURCES_CACHE"):
        directory = env[var]
        assert directory in cached, (
            f"{var} points at {directory}, which no actions/cache step persists "
            f"(cached: {sorted(cached)}); the cache would be empty on every run"
        )


def test_cache_keys_are_not_pinned_to_a_single_run():
    """A key containing only github.run_id can never be restored."""
    steps = workflow()["jobs"]["build"]["steps"]
    for s in steps:
        if not str(s.get("uses", "")).startswith("actions/cache"):
            continue
        restore = s["with"].get("restore-keys", "")
        assert restore.strip(), (
            f"cache for {s['with']['path']} has no restore-keys; its key includes "
            "github.run_id, so every run would miss and the cache would never be used"
        )
        assert "github.run_id" not in restore, (
            "restore-keys include github.run_id, which cannot match a previous run"
        )


def test_the_podman_backend_honours_the_sources_cache():
    """It did not, and that is the backend the desktop builds use."""
    text = BUILD_CHAIN.read_text()
    start = text.index("Download tarballs.")
    end = text.index("Fetch dist-git lookaside sources", start)
    assert "RPM_SOURCES_CACHE" in text[start:end], (
        "the podman path's spectool still writes only into the builddir, so "
        "RPM_SOURCES_CACHE has no effect on the desktop builds"
    )


def test_lookaside_downloads_are_persisted_only_after_verification():
    text = BUILD_CHAIN.read_text()
    start = text.index("Fetch dist-git lookaside sources")
    block = text[start:text.index('done < "$sources_file"', start)]
    # Comments in this block discuss the cache by name, and prose is not an
    # order of operations -- index the code only.
    code = "\n".join(
        line for line in block.splitlines() if not line.lstrip().startswith("#")
    )
    check = code.index("--check --quiet")
    persist = code.index("RPM_SOURCES_CACHE")
    assert check < persist, (
        "a lookaside archive is copied into the shared cache before its "
        "checksum is verified; a corrupt download would be served to every "
        "later package and run"
    )
