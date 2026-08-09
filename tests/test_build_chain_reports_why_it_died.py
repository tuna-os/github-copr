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


def test_the_dispatcher_records_the_package_in_a_global(tmp_path: Path) -> None:
    """The trap runs after the failing function has already returned.

    Its locals are popped by then, so pkg_dir is unset inside _on_error and
    dynamic scoping does not save you -- verified directly, a `local pkg_dir`
    in the caller reads as UNSET in the handler. That is why the worker banner
    printed "package: <none in scope>" for every failure in run 31294475023,
    which made an unbuildable qt6 module and #301's missing-spec bug produce
    identical output.

    A global set before dispatch survives the return.
    """
    text = SCRIPT.read_text()
    assert "CURRENT_PACKAGE=" in text, "build_package no longer records the package"
    dispatcher = text.split("build_package() {", 1)[1].split("\n}", 1)[0]
    assert "CURRENT_PACKAGE=" in dispatcher, (
        "CURRENT_PACKAGE is set somewhere other than the dispatcher, so a "
        "failure in the dispatcher itself would not be attributed"
    )
    assert "local CURRENT_PACKAGE" not in dispatcher, (
        "CURRENT_PACKAGE is local, which is exactly the bug being fixed"
    )


def test_the_trap_names_the_package_that_was_being_built(tmp_path: Path) -> None:
    handler = SCRIPT.read_text().split("_on_error() {", 1)[1].split("\n}", 1)[0]
    script = tmp_path / "t.sh"
    script.write_text(textwrap.dedent(f"""\
        set -Eeuo pipefail
        _on_error() {{{handler}
        }}
        trap _on_error ERR
        build_package() {{
            local pkg_dir="$1"
            CURRENT_PACKAGE="$(basename "$pkg_dir")"
            return 1
        }}
        build_package /src/hummingbird/qt6-qtserialport
    """))
    out = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert out.returncode != 0
    assert "qt6-qtserialport" in out.stderr, (
        f"the trap did not name the package it died on:\n{out.stderr}"
    )
    assert "<none in scope>" not in out.stderr


def test_it_still_says_none_when_there_is_genuinely_no_package(tmp_path: Path) -> None:
    """A failure outside any package must not invent one."""
    handler = SCRIPT.read_text().split("_on_error() {", 1)[1].split("\n}", 1)[0]
    script = tmp_path / "t.sh"
    script.write_text(textwrap.dedent(f"""\
        set -Eeuo pipefail
        _on_error() {{{handler}
        }}
        trap _on_error ERR
        false
    """))
    out = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert "<none in scope>" in out.stderr, out.stderr


def _mock_teardown_noise(chroot: str, lines: int = 100) -> str:
    """What mock writes to root.log AFTER the build, verbatim in shape.

    Copied from run 31294475023's python-setproctitle job: every root.log tail
    in that run was exclusively this.
    """
    out = []
    for i in range(lines):
        out.append(
            f"DEBUG util.py:558:  Executing command: ['/bin/umount', '-n', "
            f"'/var/lib/mock/{chroot}/root/dev/node{i}'] with env "
            "{'TERM': 'vt100'} and shell False"
        )
        out.append("DEBUG util.py:610:  Child return code was: 0")
    return "\n".join(out)


def _drive_with_logs(
    tmp_path: Path, build_log: str = "", root_log: str = ""
) -> subprocess.CompletedProcess:
    """Fail inside the real handler with real result logs on disk."""
    results = tmp_path / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / "build.log").write_text(build_log)
    (results / "root.log").write_text(root_log)
    return _drive_handler(tmp_path, f"""
        FILTER_TIER=layer-00
        builddir={tmp_path}
        pkg_name=demo
        false
    """)


def test_the_dnf_error_survives_mocks_teardown(tmp_path: Path) -> None:
    """The one line that explains the failure is ~90 lines above the tail.

    Run 31294475023 failed qt6-qtserialport, qt6-qtlanguageserver and
    python-setproctitle on the buildroot install. All three printed a root.log
    tail of nothing but umount DEBUG, because mock unmounts ~45 paths after the
    build and each costs two lines. Asking for more tail does not reach it: a
    failing job in that run is ~11,800 lines, since a mock failure cats
    build.log and root.log in full, and every log retrieval path returns the
    tail. So the reason has to be re-emitted last or it is unreadable.
    """
    proc = _drive_with_logs(
        tmp_path,
        root_log=(
            "DEBUG util.py:558:  Executing command: ['dnf5', 'builddep']\n"
            "DEBUG util.py:598:  Problem: conflicting requests\n"
            "DEBUG util.py:598:   - package python3-flit-core-3.12.0-1.fc45.noarch"
            " requires python(abi) = 3.15, but none of the providers can be"
            " installed\n"
            + _mock_teardown_noise("hummingbird-ci-python-setproctitle")
        ),
    )
    assert proc.returncode != 0
    assert "but none of the providers can be installed" in proc.stderr, (
        "the dnf error is still buried above mock's teardown:\n" + proc.stderr
    )
    assert "conflicting requests" in proc.stderr


def test_a_stale_patch_is_named_from_build_log(tmp_path: Path) -> None:
    """zimg died in %prep; its build.log tail carried the reason, most do not."""
    proc = _drive_with_logs(
        tmp_path,
        build_log=(
            "+ /usr/bin/patch -p1 -s --fuzz=0 --no-backup-if-mismatch -f\n"
            "1 out of 1 hunk FAILED -- saving rejects to file"
            " src/zimg/colorspace/x86/operation_impl_x86.cpp.rej\n"
            "error: Bad exit status from /var/tmp/rpm-tmp.E03Dqj (%prep)\n"
            + "\n".join(f"filler line {i}" for i in range(200))
        ),
    )
    assert "hunk FAILED" in proc.stderr, proc.stderr
    assert "Bad exit status from" in proc.stderr


def test_it_does_not_invent_a_reason_when_the_log_has_none(tmp_path: Path) -> None:
    """A 'why' section that fires on every failure is another blind tail.

    If the log carries no recognisable error shape, say nothing rather than
    print the last 20 arbitrary lines under a heading that claims they are the
    cause.
    """
    proc = _drive_with_logs(
        tmp_path, root_log=_mock_teardown_noise("hummingbird-ci-demo")
    )
    assert "why" not in proc.stderr.split("--- tail of")[0].lower().replace(
        "package build failed", ""
    ), proc.stderr
    assert "--- tail of" in proc.stderr


def test_the_handler_still_survives_an_unreadable_log(tmp_path: Path) -> None:
    """grep on a missing file must not kill the handler mid-report."""
    proc = _drive_handler(tmp_path, f"""
        FILTER_TIER=layer-00
        builddir={tmp_path}/nowhere
        false
    """)
    assert proc.returncode != 0
    assert "build-chain.sh FAILED" in proc.stderr
    assert proc.stderr.rstrip().endswith("="), (
        "the handler did not reach its closing rule:\n" + proc.stderr
    )
