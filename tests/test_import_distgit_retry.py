"""The dist-git clone retry in scripts/import-fedora-distgit.py.

The import step clones every `distgit:` package of a tier from
src.fedoraproject.org, `--jobs 8` at a time.  That burst is enough to make the
server shed load: run 31266178578 (`build (niri)`) lost 13 of 24 packages to
`fatal: the remote end hung up unexpectedly`, and an earlier attempt on the
same commit lost 17 of 24 to HTTP 503 — while the host answered a plain probe
with 200 throughout.  Because a single `git clone` was the whole story per
package, one unlucky package failed the entire import and skipped the build.

These drive the real script with a fake `git` on PATH that fails a set number
of times before succeeding.  The part a mistake would break is the boundary:
retrying too few times leaves the flake fatal, and swallowing an exhausted
retry would report a green import that copied nothing.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "import-fedora-distgit.py"

FAKE_GIT = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    # Stand-in for git: `clone` fails $FAKE_GIT_FAILURES times per package
    # before producing a checkout, `-C ... rev-parse` answers a fixed commit.
    if [ "$1" = "clone" ]; then
      dest="${@: -1}"
      url="${@: -2:1}"
      pkg="$(basename "$url" .git)"
      counter="$FAKE_GIT_STATE/$pkg"
      n=0
      [ -f "$counter" ] && n="$(cat "$counter")"
      n=$((n + 1))
      echo "$n" > "$counter"
      if [ -n "${FAKE_GIT_DEFINITIVE:-}" ]; then
        echo "Cloning into '$dest'..." >&2
        echo "$FAKE_GIT_DEFINITIVE" >&2
        exit 128
      fi
      if [ "$n" -le "${FAKE_GIT_FAILURES:-0}" ]; then
        echo "Cloning into '$dest'..." >&2
        echo "fatal: the remote end hung up unexpectedly" >&2
        exit 128
      fi
      mkdir -p "$dest/.git"
      printf 'Name: %s\\nVersion: 1\\nRelease: 1%%{?dist}\\nSummary: s\\n' "$pkg" \\
        > "$dest/$pkg.spec"
      exit 0
    fi
    if [ "$1" = "-C" ]; then
      echo 0123456789abcdef0123456789abcdef01234567
      exit 0
    fi
    exit 0
    """
)


def load_script():
    spec = importlib.util.spec_from_file_location("import_fedora_distgit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_import(
    tmp_path: Path, failures: int, attempts: int, definitive: str | None = None
) -> tuple[int, str, Path]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "git"
    fake.write_text(FAKE_GIT)
    fake.chmod(0o755)

    state = tmp_path / "attempts"
    state.mkdir()
    dest = tmp_path / "src"

    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
    env["FAKE_GIT_FAILURES"] = str(failures)
    env["FAKE_GIT_STATE"] = str(state)
    if definitive:
        env["FAKE_GIT_DEFINITIVE"] = definitive

    proc = subprocess.run(
        [
            "python3", str(SCRIPT),
            "--package", "libmpdclient",
            "--dest", str(dest),
            "--clone-attempts", str(attempts),
            "--jobs", "1",
        ],
        capture_output=True, text=True, env=env, cwd=tmp_path,
    )
    return proc.returncode, proc.stdout + proc.stderr, dest


def test_transient_clone_failures_are_retried(tmp_path):
    """Two hangups inside a four-attempt budget still import the package."""
    code, output, dest = run_import(tmp_path, failures=2, attempts=4)

    assert code == 0, output
    assert "imported=1" in output
    assert "failed=0" in output
    assert (dest / "libmpdclient" / "libmpdclient.spec").exists()
    # The retries are announced, so a flaky import is visible in the CI log
    # rather than looking like a clean first-try clone.
    assert output.count("Retrying libmpdclient") == 2


def test_exhausted_retries_still_fail_the_import(tmp_path):
    """Retrying must not turn a genuinely unreachable package into success."""
    code, output, dest = run_import(tmp_path, failures=99, attempts=2)

    assert code == 1, output
    assert "FAILED libmpdclient: fatal: the remote end hung up unexpectedly" in output
    assert "imported=0" in output
    assert "failed=1" in output
    assert not (dest / "libmpdclient").exists()


def test_partial_checkout_does_not_block_the_next_attempt(tmp_path):
    """git refuses to clone into a non-empty directory.

    The fake writes into $dest only on success, so this asserts the property
    that matters instead: a package that fails then succeeds ends up with a
    complete checkout, not one merged from two attempts.
    """
    code, output, dest = run_import(tmp_path, failures=1, attempts=4)

    assert code == 0, output
    files = sorted(p.name for p in (dest / "libmpdclient").iterdir())
    assert files == ["libmpdclient.spec"], files


def test_missing_package_is_not_retried(tmp_path):
    """A manifest bug must surface on the first attempt, not after the budget.

    A package or branch that does not exist fails identically forever, so
    retrying only delays the report by the whole backoff window.
    """
    code, output, _ = run_import(
        tmp_path, failures=0, attempts=4,
        definitive="fatal: repository 'https://src.fedoraproject.org/rpms/libmpdclient.git' not found",
    )

    assert code == 1, output
    assert "Retrying" not in output
    assert "failed=1" in output


def test_missing_branch_is_not_retried(tmp_path):
    code, output, _ = run_import(
        tmp_path, failures=0, attempts=4,
        definitive="fatal: Remote branch rawhide not found in upstream origin",
    )

    assert code == 1, output
    assert "Retrying" not in output


def test_transient_and_definitive_are_told_apart():
    module = load_script()

    assert not module.is_definitive_failure("fatal: the remote end hung up unexpectedly")
    assert not module.is_definitive_failure("error: RPC failed; HTTP 503")
    assert not module.is_definitive_failure("fatal: unable to access ...: Empty reply from server")

    assert module.is_definitive_failure("fatal: repository 'https://x/y.git' not found")
    assert module.is_definitive_failure("fatal: Remote branch rawhide not found in upstream origin")
    assert module.is_definitive_failure("fatal: Authentication failed for 'https://x/'")


def test_backoff_is_bounded_and_grows():
    module = load_script()

    for attempt in range(1, 8):
        ceiling = min(module.BACKOFF_CAP, module.BACKOFF_BASE * (2 ** (attempt - 1)))
        for _ in range(50):
            delay = module.backoff_delay(attempt)
            assert 0.0 <= delay <= ceiling

    # Capped, so a long outage cannot back off into the job timeout.
    assert module.backoff_delay(20) <= module.BACKOFF_CAP
