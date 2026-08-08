"""The dist-git clone retry in scripts/import-fedora-distgit.py.

src.fedoraproject.org throttles concurrent clones.  The import step runs eight
at a time, and the server answers part of the batch with HTTP 503 or drops the
connection ("fatal: the remote end hung up unexpectedly") -- a different subset
of packages each time.  Run 31266178578 lost 17 of its 24 clones that way, and
the rerun of the same commit lost 13, with only three packages failing in both.
With one attempt per package that is a failed import and a red job, for nothing
that is wrong with the repository.

What a mistake here would break: retrying nothing leaves the flake in place,
and retrying everything turns a package that genuinely is not in dist-git (or a
branch that does not exist) into four attempts and a slow, misleading failure.
So both halves are pinned -- transient failures are retried, definitive "not
found" answers are not.

The real network is not involved: a stub `git` earlier on PATH plays the
server, and records how many times each package was asked for.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "import-fedora-distgit.py"

# `git clone --depth 1 --branch <branch> <url> <dest>`: $7 is the destination.
STUB_GIT = """#!/usr/bin/env bash
set -u
if [ "$1" = "clone" ]; then
    pkg="$(basename "$7")"
    attempts="$STUB_STATE/$pkg.attempts"
    printf 'x' >> "$attempts"
    n=$(wc -c < "$attempts")
    if [ -n "${STUB_FATAL:-}" ] && [ "$pkg" = "$STUB_FATAL" ]; then
        echo "fatal: Remote branch rawhide not found in upstream origin" >&2
        exit 128
    fi
    if [ "$n" -le "${STUB_FAIL_TIMES:-0}" ]; then
        echo "fatal: the remote end hung up unexpectedly" >&2
        exit 128
    fi
    mkdir -p "$7"
    echo "Name: $pkg" > "$7/$pkg.spec"
    exit 0
fi
if [ "$1" = "-C" ]; then
    echo 0123456789abcdef0123456789abcdef01234567
    exit 0
fi
exit 1
"""


def run_import(tmp_path: Path, package: str, *, fail_times: int = 0, fatal: str = "") -> tuple[
    subprocess.CompletedProcess[str], int
]:
    """Import one package against the stub server.

    Returns the finished process and the number of clone attempts it made.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "git").write_text(STUB_GIT)
    (bindir / "git").chmod(0o755)
    state = tmp_path / "state"
    state.mkdir()

    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "STUB_STATE": str(state),
        "STUB_FAIL_TIMES": str(fail_times),
        "STUB_FATAL": fatal,
    }
    proc = subprocess.run(
        [
            "python3", str(SCRIPT),
            "--package", package,
            "--dest", str(tmp_path / "out"),
            "--state", str(tmp_path / "imports.json"),
        ],
        capture_output=True, text=True, cwd=tmp_path, env=env,
    )
    attempts = state / f"{package}.attempts"
    return proc, len(attempts.read_bytes()) if attempts.exists() else 0


def test_transient_failure_is_retried_until_it_succeeds(tmp_path):
    proc, attempts = run_import(tmp_path, "cliphist", fail_times=2)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert attempts == 3
    assert "imported=1" in proc.stdout
    assert "failed=0" in proc.stdout
    # The import is only real if the packaging actually landed.
    assert (tmp_path / "out" / "cliphist" / "cliphist.spec").exists()
    assert json.loads((tmp_path / "imports.json").read_text())["cliphist"]["commit"]


def test_transient_failure_that_never_clears_still_fails_the_import(tmp_path):
    proc, attempts = run_import(tmp_path, "cliphist", fail_times=99)

    assert proc.returncode == 1
    assert attempts == 4, "retries are bounded, not endless"
    assert "FAILED cliphist after 4 attempts" in proc.stdout
    assert "failed=1" in proc.stdout


def test_a_package_that_does_not_exist_is_not_retried(tmp_path):
    proc, attempts = run_import(tmp_path, "not-a-package", fatal="not-a-package")

    assert proc.returncode == 1
    assert attempts == 1, "a missing package or branch is a manifest bug, not a flake"
    assert "FAILED not-a-package:" in proc.stdout
