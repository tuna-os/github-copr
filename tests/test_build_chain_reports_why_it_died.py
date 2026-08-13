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


def test_the_reason_is_pulled_out_of_the_middle_of_root_log(tmp_path: Path) -> None:
    """A tail of root.log is the dnf summary, not the reason.

    dnf prints the "Problem:" chain when it gives up resolving, then keeps
    going for hundreds of lines of transaction bookkeeping. `tail -n 40`
    therefore reliably returns the part that says nothing. Getting at the real
    line meant downloading the run's whole log archive -- which, for one
    Hummingbird run, was a multi-megabyte zip that failed to transfer twice
    before being abandoned.

    So the handler greps the reasons out and prints them ahead of the tail.
    """
    builddir = tmp_path / "build"
    (builddir / "results").mkdir(parents=True)
    (builddir / "results" / "root.log").write_text(
        "\n".join(
            ["DEBUG util.py:1 preparing transaction"]
            + ["Problem: conflicting requests"]
            + ["  - nothing provides perl(:MODULE_COMPAT_5.42.0) needed by libfoo-1.0"]
            # Enough bookkeeping after it to push the reason clear of any tail.
            + [f"DEBUG util.py:{i} Installing : filler-{i}.noarch" for i in range(200)]
        )
    )

    proc = _drive_handler(tmp_path, f"""
        FILTER_TIER=demo
        builddir={builddir}
        pkg_name=libfoo
        false
    """)

    assert proc.returncode != 0
    assert "why" in proc.stderr and "root.log" in proc.stderr, (
        f"no reason section emitted: {proc.stderr!r}"
    )
    assert "nothing provides perl(:MODULE_COMPAT_5.42.0)" in proc.stderr, (
        "the handler printed a tail but not the line that explains the "
        f"failure: {proc.stderr!r}"
    )
    assert "Problem: conflicting requests" in proc.stderr


def test_a_tail_alone_would_have_missed_it(tmp_path: Path) -> None:
    """Guards the premise of the test above rather than assuming it.

    If the filler ever stops being long enough to push the reason out of the
    last 40 lines, the test above would pass on a handler that only tails, and
    silently stop testing anything.
    """
    builddir = tmp_path / "build"
    (builddir / "results").mkdir(parents=True)
    log = builddir / "results" / "root.log"
    log.write_text(
        "\n".join(
            ["Problem: conflicting requests"]
            + [f"DEBUG util.py:{i} Installing : filler-{i}.noarch" for i in range(200)]
        )
    )
    tail = log.read_text().splitlines()[-40:]
    assert not any("Problem:" in line for line in tail), (
        "the reason is inside the last 40 lines, so this fixture no longer "
        "distinguishes a grep from a tail"
    )


def test_a_log_with_no_reason_in_it_still_gets_its_tail(tmp_path: Path) -> None:
    """grep exits 1 on no match, and it must not cost us the tail.

    Note what does NOT protect this: `_on_error` runs `set +e` on its first
    line, so `set -e` is already off by the time the grep runs. The `|| true`
    on that line is defence for a future edit that removes the `set +e`, not
    the thing keeping this green today -- removing it changes nothing
    observable, so this test deliberately does not claim to pin it.

    What this does pin is the shape of the output when a log holds no
    recognised reason, which is the common case for a package that failed at
    compile time rather than in the buildroot: the tail still appears, and no
    empty "why" banner appears above it promising an explanation that is not
    there.
    """
    builddir = tmp_path / "build"
    (builddir / "results").mkdir(parents=True)
    (builddir / "results" / "build.log").write_text("everything was fine here\n")

    proc = _drive_handler(tmp_path, f"""
        FILTER_TIER=demo
        builddir={builddir}
        false
    """)
    assert "build-chain.sh FAILED" in proc.stderr
    assert "tail of" in proc.stderr, (
        f"handler stopped short after an empty grep: {proc.stderr!r}"
    )
    assert "why" not in proc.stderr, (
        "an empty reason section was printed for a log with no reason in it, "
        f"which reads as 'the cause is nothing': {proc.stderr!r}"
    )
