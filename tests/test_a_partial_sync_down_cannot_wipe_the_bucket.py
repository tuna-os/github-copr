"""A swallowed sync-down failure deletes packages from the bucket.

Every RPM publisher here does sync-down -> sign/index -> sync-up, and
`rclone sync` makes the DESTINATION MATCH THE SOURCE. So the sync-up at the
end deletes from the bucket anything that is not in the local tree. If the
sync-down at the start partially fails and the failure is swallowed, the
sync-up erases exactly the objects that failed to arrive.

That is #124 / INCIDENT-repo-wipe-gnome, and it happened again: between
2026-08-20 and 2026-08-25, repo/10/x86_64 lost ~160 served package names,
among them gdk-pixbuf2, harfbuzz, gnome-desktop3 and malcontent (#519).

Those are dependencies, not leaves. gnome-shell, mutter and gtk4 were still
IN the index -- so dnf reported them as BROKEN rather than unavailable, and
`--skip-unavailable` dropped gtk4 plus 17 others without failing the build.
tunaOS then published `hummingbird:gnome` with 410 packages: gnome
wallpapers, gnome docs, and no GNOME. The first thing that noticed was a
boot gate timing out 15 minutes later.

publish-rpm-wave.sh's NEVER SHRINK guard cannot catch this. It counts RPMs
in the local tree, and the lost files were never synced down to be counted.
The guard has to live at the sync-down.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _sync_down_publishers():
    """Workflows that sync a repo prefix down and later sync it back up."""
    out = []
    for f in sorted(WORKFLOWS.glob("*.yml")):
        text = f.read_text(encoding="utf-8")
        if re.search(r'rclone sync "r2:\$\{R2_BUCKET\}/[^"]+" repo/', text) and re.search(
            r'rclone sync repo/ "r2:\$\{R2_BUCKET\}', text
        ):
            out.append((f, text))
    return out


def test_there_is_something_to_check():
    """Guard the guard: a rename must not silently empty this suite."""
    found = _sync_down_publishers()
    assert found, (
        "no workflow matched the sync-down/sync-up shape — either the "
        "publishers were renamed or this test has gone blind"
    )


def test_no_publisher_swallows_its_sync_down():
    offenders = []
    for path, text in _sync_down_publishers():
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("#"):
                continue
            if "rclone sync" in s and "repo/" in s and s.endswith("|| true"):
                offenders.append(f"{path.name}: {s}")
            # The continuation form: `rclone sync ... \` then `--exclude ... || true`
            if s.startswith("--exclude") and s.endswith("|| true"):
                offenders.append(f"{path.name}: {s}")
    assert not offenders, (
        "a sync-down whose failure is swallowed by `|| true`; the sync-up in "
        "the same job will DELETE whatever failed to come down:\n  "
        + "\n  ".join(offenders)
    )


def test_a_failed_sync_down_stops_before_the_destructive_sync_up():
    """Exit 3 is first-publish; anything else must abort the job."""
    for path, text in _sync_down_publishers():
        assert "_sync_rc" in text, f"{path.name}: sync-down status is never captured"
        assert "_sync_rc == 3" in text, (
            f"{path.name}: must special-case rclone exit 3 (directory not "
            "found), or the very first publish to a new prefix fails"
        )
        assert re.search(r"_sync_rc != 0.*\n.*::error::", text) or (
            "_sync_rc != 0" in text and "exit 1" in text
        ), f"{path.name}: a non-zero sync-down must exit 1, not continue"


def test_the_abort_happens_before_the_sync_up():
    for path, text in _sync_down_publishers():
        down = text.index('rclone sync "r2:${R2_BUCKET}')
        up = text.index('rclone sync repo/ "r2:${R2_BUCKET}')
        guard = text.index("_sync_rc != 0")
        assert down < guard < up, (
            f"{path.name}: the sync-down guard must sit between the sync-down "
            "and the sync-up to be able to prevent the deletion"
        )
