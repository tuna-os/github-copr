"""Every workflow that runs the cell script must supply what its engine reads.

scripts/run-package-factory-cell.sh hard-requires variables via `${VAR:?}`.
A caller that omits one fails at the first line that reads it -- after the
checkout, the apt-get and the image pull have all been paid for -- with a
message naming the variable but not the caller.

That is how the first dispatch of publish-build-chain-rpms.yml died:

    run-package-factory-cell.sh: line 14: SOURCE_DATE_EPOCH: parameter null
    or not set

Every unit test around that workflow passed. They covered the planner and the
wave script -- the parts written in Python and bash -- and not the YAML glue
between them, which is where the defect was.

Two things this test has to model correctly, both learned by getting them
wrong first:

  ENGINE BRANCHES  the requirement is not one flat list. CELL_ID, ENGINE,
                   TARGET, ARCHITECTURE, IMAGE and SOURCE_DATE_EPOCH are read
                   before the branch; MANIFEST and MOCK_CONFIG only on the
                   build-chain path, which then `exit 0`s; RECIPE and FORMAT
                   only on the tideforge path. Demanding all ten of every
                   caller flags the working publisher.

  HOW IT ARRIVES   a variable can come from workflow env, job env, step env,
                   or be assigned inside the run block. publish-tideforge
                   -rpms.yml computes SOURCE_DATE_EPOCH with `git log` in the
                   script body and exports it there. Checking only `env:`
                   keys reports a false failure.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run-package-factory-cell.sh"
WORKFLOWS = ROOT / ".github" / "workflows"

_REQUIRED = re.compile(r"\$\{([A-Z_][A-Z0-9_]*):\?")
_BUILD_CHAIN_GUARD = "if [[ $engine == build-chain ]]; then"
_TIDEFORGE_GUARD = "[[ $engine == tideforge ]]"


def _requirements():
    """(always, build_chain_only, tideforge_only) variable names."""
    text = RUNNER.read_text()
    bc_start = text.index(_BUILD_CHAIN_GUARD)
    tf_start = text.index(_TIDEFORGE_GUARD)
    always = set(_REQUIRED.findall(text[:bc_start]))
    build_chain = set(_REQUIRED.findall(text[bc_start:tf_start])) - always
    tideforge = set(_REQUIRED.findall(text[tf_start:])) - always
    return always, build_chain, tideforge


ALWAYS, BUILD_CHAIN_ONLY, TIDEFORGE_ONLY = _requirements()


def _callers():
    out = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text()
        if "run-package-factory-cell.sh" not in text:
            continue
        doc = yaml.safe_load(text)
        wf_env = set((doc.get("env") or {}).keys())
        for job in (doc.get("jobs") or {}).values():
            job_env = set((job.get("env") or {}).keys())
            for step in (job.get("steps") or []):
                body = step.get("run") or ""
                if "run-package-factory-cell.sh" not in body:
                    continue
                step_env = dict(step.get("env") or {})
                # A variable may also be assigned or exported in the body.
                assigned = set(re.findall(r"^\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)=", body, re.M))
                out.append({
                    "path": path,
                    "engine": str(step_env.get("ENGINE", job.get("env", {}).get("ENGINE", ""))),
                    "supplied": wf_env | job_env | set(step_env) | assigned,
                })
    return out


CALLERS = _callers()


def test_the_requirement_split_is_not_vacuous() -> None:
    """Guards the guard: a parse that found nothing would pass everything."""
    assert "SOURCE_DATE_EPOCH" in ALWAYS
    assert "MANIFEST" in BUILD_CHAIN_ONLY
    assert "RECIPE" in TIDEFORGE_ONLY


def test_callers_are_found() -> None:
    assert CALLERS, "no workflow appears to run run-package-factory-cell.sh"


@pytest.mark.parametrize("caller", CALLERS, ids=lambda c: f"{c['path'].name}:{c['engine'] or '?'}")
def test_every_caller_supplies_what_its_engine_reads(caller) -> None:
    needed = set(ALWAYS)
    engine = caller["engine"]
    if engine == "build-chain":
        needed |= BUILD_CHAIN_ONLY
    elif engine == "tideforge":
        needed |= TIDEFORGE_ONLY
    else:
        # An engine chosen at runtime (a matrix expression) could take either
        # branch, so it must satisfy both.
        needed |= BUILD_CHAIN_ONLY | TIDEFORGE_ONLY

    missing = needed - caller["supplied"]
    assert not missing, (
        f"{caller['path'].name} runs the cell script with ENGINE="
        f"{engine or '<dynamic>'} but does not supply {sorted(missing)}; "
        "the script exits on the first one it reads, after the checkout and "
        "the image pull have already been paid for"
    )
