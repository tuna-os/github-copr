"""build-chain.sh must say why it died, as the last thing in the log.

`set -e` kills the script the moment an unhandled command fails -- before the
end-of-run summary that names failed packages. When that happens partway
through a tier, the reason sits in the middle of a log that can be hundreds of
MB, and every practical way of reading a CI log returns the TAIL.

Measured: six independent retrieval paths were tried against one failed
Hummingbird run -- job logs three ways, check-run annotations twice, and the
web UI -- and not one returned the failing line. The run reduced to "Process
completed with exit code 1" with no package named. Four candidate causes were
proposed and eliminated without ever seeing the actual error.

An ERR trap costs nothing on the happy path and puts the failure last, so the
tail always carries it.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build-chain.sh"


def test_errtrace_is_enabled() -> None:
    """Without -E the trap never fires for a failure inside a function.

    Every real failure is inside build_package_podman, so a trap without
    errtrace is decorative. Verified by regression: with plain `set -e` the
    trap did not print for a command-not-found inside ensure_local_repo.
    """
    text = SCRIPT.read_text()
    assert "set -eEuo pipefail" in text, (
        "build-chain.sh does not enable errtrace (-E), so the ERR trap is not "
        "inherited by functions or subshells and will not fire where failures "
        "actually happen"
    )


def test_an_err_trap_is_installed() -> None:
    text = SCRIPT.read_text()
    assert "trap _on_error ERR" in text, "no ERR trap -- failures die silently"


def test_the_handler_reports_what_is_needed_to_act() -> None:
    """Exit status alone is what made the original run unactionable."""
    text = SCRIPT.read_text()
    for field in ("exit status", "at line", "command", "tier filter", "package"):
        assert field in text, f"the failure handler never reports {field!r}"


def test_the_handler_cannot_itself_fail(tmp_path: Path) -> None:
    """A diagnostic that dies while reporting a death tells you less than none.

    Drives the real handler with no build directory and no package in scope --
    the state it is in when the script dies early, which is exactly when it
    matters most.
    """
    harness = tmp_path / "harness.sh"
    body = SCRIPT.read_text().split("SCRIPT_DIR=", 1)[0]
    harness.write_text(body + textwrap.dedent("""
        FILTER_TIER=demo
        false
    """))
    proc = subprocess.run(["bash", str(harness)], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "build-chain.sh FAILED" in proc.stderr, (
        f"handler produced no report: {proc.stderr!r}"
    )
    assert "tier filter : demo" in proc.stderr


def _drive_handler(tmp_path: Path, epilogue: str) -> subprocess.CompletedProcess:
    """Run the real trap preamble followed by `epilogue`."""
    harness = tmp_path / "harness.sh"
    body = SCRIPT.read_text().split("SCRIPT_DIR=", 1)[0]
    harness.write_text(body + textwrap.dedent(epilogue))
    return subprocess.run(["bash", str(harness)], capture_output=True, text=True)


def test_it_names_the_command_that_actually_failed(tmp_path: Path) -> None:
    """`command : main` is not a diagnostic.

    The handler used to read a DEBUG trap. DEBUG is not inherited by functions
    or subshells without `set -T`, so it only ever recorded the top-level
    `main "$@"` -- i.e. every in-function death, which is all of them. Run
    31264779379 died inside build_package_podman and reported `main`.

    `set -T` is not the fix: functrace also makes RETURN traps inherited, and
    this script hangs `rm -rf "$builddir"` off RETURN.
    """
    proc = _drive_handler(tmp_path, """
        FILTER_TIER=demo
        inner() { nosuchcommand_xyz --flag; }
        outer() { inner; }
        outer
    """)
    assert proc.returncode != 0
    assert "command     : nosuchcommand_xyz --flag" in proc.stderr, (
        f"handler did not name the failing command: {proc.stderr!r}"
    )
    assert "command     : main" not in proc.stderr


def test_a_failed_package_does_not_claim_the_script_died(tmp_path: Path) -> None:
    """Packages build in background subshells, which -E hands this trap too.

    Run 31264779379 printed "build-chain.sh FAILED" three times and died of
    none of them: each was one worker exiting on an ordinary package failure
    that the tier loop recorded and carried on from. A banner that cries abort
    during normal operation trains the reader to ignore it.
    """
    proc = _drive_handler(tmp_path, """
        FILTER_TIER=demo
        pkg_name=somepkg
        ( false ) &
        wait $! || echo "parent still running" >&2
        echo "reached the end" >&2
    """)
    assert proc.returncode == 0, (
        f"a worker failure must not kill the script: {proc.stderr!r}"
    )
    assert "reached the end" in proc.stderr
    assert "build-chain.sh FAILED" not in proc.stderr, (
        f"worker failure claimed the script died: {proc.stderr!r}"
    )
    assert "package build FAILED (worker)" in proc.stderr, (
        f"worker failure went unreported: {proc.stderr!r}"
    )
    assert "package     : somepkg" in proc.stderr
