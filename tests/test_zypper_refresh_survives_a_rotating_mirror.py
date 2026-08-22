"""A Tumbleweed mirror caught mid-rotation must not turn the gate red.

openSUSE publishes snapshots frequently and download.opensuse.org is a
REDIRECTOR to mirrors that sync at different speeds. A mirror partway through
serves a repomd.xml naming files it has not received yet, and zypper rejects
the whole repository:

    Repository 'openSUSE-Tumbleweed-Oss' is invalid.
    [repo-oss|...] Failed to retrieve new repository metadata.
     - File './repodata/dbe06c23...-appdata-icons.tar.gz' not found on medium
    No provider of 'rpmlint' found.

That failed tideforge-wayland-protocols-opensuse-tumbleweed-x86_64 in run
32586260792 at 16:57:59Z. Measured minutes later: all 20 files repomd.xml
lists resolve 200, and so does that exact appdata-icons.tar.gz. Nothing was
wrong with the repository or with the recipe.

The behaviour is exercised against a fake zypper rather than asserted from the
source text, because the thing that matters is what the loop DOES on the
second attempt -- and the failure mode this guards against (retrying without
clearing the cached repomd, so every attempt re-reads the same index naming
the same absent file) is invisible to a grep for "retry".
"""
from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "zypper-refresh-with-retry.sh"
CELL = ROOT / "scripts" / "run-package-factory-cell.sh"


def run_with_fake_zypper(tmp_path: Path, body: str, **env: str) -> subprocess.CompletedProcess:
    """Run the script with `zypper` replaced by a stub that logs its calls."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    fake = bin_dir / "zypper"
    fake.write_text(
        textwrap.dedent(f"""\
        #!/usr/bin/env bash
        echo "$*" >> {log}
        STATE={tmp_path}/attempts
        {body}
        """),
        encoding="utf-8",
    )
    fake.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "ZYPPER_REFRESH_DELAY": "0",
        **env,
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, env=environment
    )
    result.log = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result


REFRESH_FAILS_ONCE = """\
count=$(cat "$STATE" 2>/dev/null || echo 0)
case "$*" in
  *refresh*)
    count=$((count + 1)); echo "$count" > "$STATE"
    if [ "$count" -le 1 ]; then
      echo "File './repodata/abc-appdata-icons.tar.gz' not found on medium" >&2
      exit 6
    fi
    exit 0 ;;
  *) exit 0 ;;
esac
"""

REFRESH_ALWAYS_FAILS = """\
case "$*" in
  *refresh*) echo "some other real error" >&2; exit 6 ;;
  *) exit 0 ;;
esac
"""


@pytest.fixture
def bash_available():
    if not shutil.which("bash"):
        pytest.skip("bash unavailable")


def test_the_script_exists_and_is_executable(bash_available):
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)


def test_a_transient_mirror_failure_is_survived(tmp_path, bash_available):
    result = run_with_fake_zypper(tmp_path, REFRESH_FAILS_ONCE)
    assert result.returncode == 0, result.stderr
    assert sum("refresh" in call for call in result.log) == 2


def test_the_cached_metadata_is_cleared_between_attempts(tmp_path, bash_available):
    """The whole point. zypper caches the repomd it already fetched, so a
    retry that does not clear it re-reads the same index naming the same
    absent file and can never succeed."""
    result = run_with_fake_zypper(tmp_path, REFRESH_FAILS_ONCE)
    refresh_at = [i for i, call in enumerate(result.log) if "refresh" in call]
    clean_at = [i for i, call in enumerate(result.log) if "clean" in call and "metadata" in call]
    assert clean_at, f"no metadata clean between attempts: {result.log}"
    assert refresh_at[0] < clean_at[0] < refresh_at[1], result.log


def test_a_real_failure_still_fails(tmp_path, bash_available):
    """Bounded attempts. A retry that never gives up converts a broken
    repository into a 180-minute timeout, which is strictly worse than a fast
    red."""
    result = run_with_fake_zypper(tmp_path, REFRESH_ALWAYS_FAILS, ZYPPER_REFRESH_ATTEMPTS="3")
    assert result.returncode != 0
    assert sum("refresh" in call for call in result.log) == 3


def test_it_succeeds_without_retrying_when_the_mirror_is_healthy(tmp_path, bash_available):
    result = run_with_fake_zypper(tmp_path, "exit 0")
    assert result.returncode == 0
    assert sum("refresh" in call for call in result.log) == 1


def test_the_gpg_auto_import_is_preserved(tmp_path, bash_available):
    """The flag the inline command carried; dropping it would make the first
    refresh prompt and hang instead of failing."""
    result = run_with_fake_zypper(tmp_path, "exit 0")
    assert any("--gpg-auto-import-keys" in call for call in result.log), result.log


def test_the_cell_runner_calls_it_instead_of_zypper_refresh_directly():
    text = CELL.read_text(encoding="utf-8")
    assert "zypper-refresh-with-retry.sh" in text
    assert "--gpg-auto-import-keys refresh" not in text, "an un-retried refresh survived"


def test_the_scripts_directory_is_mounted_for_the_opensuse_container():
    """The script has to be reachable from inside the container, or the cell
    dies on 'No such file or directory' at the first build."""
    text = CELL.read_text(encoding="utf-8")
    opensuse = text[text.index("opensuse-tumbleweed ]]"):]
    opensuse = opensuse[: opensuse.index("rpmbuild -ba")]
    assert '--volume "$PWD/scripts:/scripts:ro"' in opensuse
    assert "/scripts/zypper-refresh-with-retry.sh" in opensuse
