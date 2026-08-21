"""The publish wave's safety rules, pinned against the incidents that taught them.

publish-rpm-wave.sh is shared by publish-tideforge-rpms.yml and
publish-build-chain-rpms.yml. Sharing it is the point: every rule here was
learned once, and a second hand-copied publisher would have to learn each of
them again. This repo has already paid for that twice -- the nightly cron
stagger that was documented but never applied, and the readiness stamp read
from two paths flatpak had stopped using.

The rules under test:

  empty wave    a build that produced nothing must not look published
  never shrink  #124: `rclone sync` deletes whatever the local tree lacks
  '+' renaming  run 32411090239: '+' in a filename 404s through the worker
  srpms         source RPMs are not installable content
"""
from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publish-rpm-wave.sh"


@pytest.fixture
def stubbed(tmp_path):
    """rpmsign and createrepo_c stubbed; they need a keyring and a real repo."""
    binq = tmp_path / "bin"
    binq.mkdir()
    for tool in ("rpmsign", "createrepo_c"):
        p = binq / tool
        p.write_text(f'#!/bin/sh\necho "{tool} $*" >> "$STUB_LOG"\nexit 0\n')
        p.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{binq}:{env['PATH']}"
    env["STUB_LOG"] = str(tmp_path / "stub.log")
    (tmp_path / "stub.log").write_text("")
    return env


def run(tmp_path, env, staged="staged", repo="repo", subdir="build-chain"):
    return subprocess.run(
        ["bash", str(SCRIPT), "--staged", str(tmp_path / staged),
         "--repo", str(tmp_path / repo), "--subdir", subdir],
        capture_output=True, text=True, env=env, cwd=tmp_path,
    )


def make(dirpath: Path, *names):
    dirpath.mkdir(parents=True, exist_ok=True)
    for n in names:
        (dirpath / n).write_text("rpm")


def rpms(root: Path):
    return sorted(p.name for p in root.rglob("*.rpm"))


# --- empty wave -------------------------------------------------------------


def test_an_empty_wave_is_refused(tmp_path, stubbed) -> None:
    """A build that produced nothing must not rewrite repodata and look green."""
    make(tmp_path / "staged")
    r = run(tmp_path, stubbed)
    assert r.returncode == 1
    assert "empty wave" in r.stderr


def test_a_wave_of_only_srpms_is_an_empty_wave(tmp_path, stubbed) -> None:
    make(tmp_path / "staged", "foo-1.0.src.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 1
    assert "empty wave" in r.stderr


# --- the happy path ---------------------------------------------------------


def test_binary_rpms_are_signed_and_placed(tmp_path, stubbed) -> None:
    make(tmp_path / "staged", "foo-1.0.el10.x86_64.rpm", "bar-2.0.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    placed = tmp_path / "repo" / "build-chain"
    assert rpms(placed) == ["bar-2.0.el10.x86_64.rpm", "foo-1.0.el10.x86_64.rpm"]
    log = (tmp_path / "stub.log").read_text()
    assert log.count("rpmsign") == 2
    assert "createrepo_c" in log


def test_srpms_are_not_published(tmp_path, stubbed) -> None:
    make(tmp_path / "staged", "foo-1.0.el10.x86_64.rpm", "foo-1.0.src.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert rpms(tmp_path / "repo") == ["foo-1.0.el10.x86_64.rpm"]


def test_existing_packages_are_preserved(tmp_path, stubbed) -> None:
    """The sync-down content must survive; publishing adds, never replaces."""
    make(tmp_path / "repo" / "tideforge", "already-1.0.el10.x86_64.rpm")
    make(tmp_path / "staged", "new-1.0.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert rpms(tmp_path / "repo") == [
        "already-1.0.el10.x86_64.rpm", "new-1.0.el10.x86_64.rpm"
    ]


# --- the '+' rename ---------------------------------------------------------


def test_plus_is_renamed_in_staged_files(tmp_path, stubbed) -> None:
    """run 32411090239: the %2b URL 404s through the repo.tunaos.org worker."""
    make(tmp_path / "staged", "oversteer-udev-0.8.3+git74c7484.el10.noarch.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert rpms(tmp_path / "repo") == [
        "oversteer-udev-0.8.3.git74c7484.el10.noarch.rpm"
    ]


def test_plus_is_renamed_in_files_synced_down_too(tmp_path, stubbed) -> None:
    """Otherwise the sync leaves the already-broken object in the bucket."""
    make(tmp_path / "repo" / "tideforge", "old-1.0+git.el10.x86_64.rpm")
    make(tmp_path / "staged", "new-1.0.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert "old-1.0.git.el10.x86_64.rpm" in rpms(tmp_path / "repo")
    assert not any("+" in n for n in rpms(tmp_path / "repo"))


# --- never shrink -----------------------------------------------------------


def test_the_count_never_shrinks_on_the_happy_path(tmp_path, stubbed) -> None:
    make(tmp_path / "repo" / "tideforge", *[f"p{i}.el10.x86_64.rpm" for i in range(5)])
    make(tmp_path / "staged", "new.el10.x86_64.rpm")
    r = run(tmp_path, stubbed)
    assert r.returncode == 0, r.stderr
    assert len(rpms(tmp_path / "repo")) == 6
    assert "repo already holds 5" in r.stdout
    assert "repo now holds 6" in r.stdout


def test_a_shrinking_tree_is_refused(tmp_path, stubbed) -> None:
    """#124: syncing up from a smaller tree DELETES the difference.

    Simulated by making the copy step lose files -- a stubbed `cp` that
    drops them stands in for whatever real cause (disk, permissions, a bad
    find) would produce the same shape.
    """
    make(tmp_path / "repo" / "tideforge", *[f"p{i}.el10.x86_64.rpm" for i in range(5)])
    make(tmp_path / "staged", "new.el10.x86_64.rpm")

    # A `cp` that silently drops the file, and a `mv` that deletes instead of
    # renaming, together shrink the tree the way a real fault would.
    sabotage = Path(stubbed["PATH"].split(":")[0]) / "cp"
    sabotage.write_text(
        "#!/bin/sh\n"
        # consume `-t DEST FILES...`, then delete two pre-existing files
        f"rm -f {tmp_path}/repo/tideforge/p0.el10.x86_64.rpm "
        f"{tmp_path}/repo/tideforge/p1.el10.x86_64.rpm\n"
        "exit 0\n"
    )
    sabotage.chmod(0o755)

    r = run(tmp_path, stubbed)
    assert r.returncode == 1
    assert "shrank from 5 to 3" in r.stderr
    assert "DELETES" in r.stderr


# --- interface --------------------------------------------------------------


def test_missing_arguments_are_refused(tmp_path, stubbed) -> None:
    r = subprocess.run(
        ["bash", str(SCRIPT), "--staged", str(tmp_path)],
        capture_output=True, text=True, env=stubbed,
    )
    assert r.returncode == 2
    assert "usage:" in r.stderr
