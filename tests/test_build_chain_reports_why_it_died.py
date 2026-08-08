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
