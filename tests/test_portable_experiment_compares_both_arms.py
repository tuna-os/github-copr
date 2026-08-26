"""The portable experiment must gate BOTH arms and compare them.

Run 32946019180 reported eight red carriers and a green native arm, and the
comparison behind that was not a comparison. `run-package-factory-cell.sh`
builds and packages; it does not verify. The lint/install/smoke gate is
invoked by the workflow (package-factory-cell.yml:270), so the baseline job --
which called only the cell script, with `set +e` around it -- never ran the
gate and could not fail. The portable arm ran it and was failed by it.

The eight failures were real unmet dependencies, and none of them was about
portability: dms declares `runtime: common: [quickshell]` and no el10
published index serves quickshell, so the target-native package cannot
clean-install either. The experiment was failing carriers for facts about the
recipe.

So the bar is PARITY, not absolute success: a carrier must never fail a gate
its native counterpart passes. Both-red is information, not a defect.

These tests run the workflow's own inline comparison script rather than a
paraphrase of it, because a paraphrase that alone learns the rule passes
while the workflow still ships the old one.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tideforge-portable-experiment.yml"
SPEC = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def step(job: str, name: str) -> dict:
    for entry in SPEC["jobs"][job]["steps"]:
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"{job} has no step named {name!r}")


def comparison_script() -> str:
    body = step("benchmark", "Compare compilation work")["run"]
    match = re.search(r"python3 - <<'PY'\n(.*)\nPY\n?$", body, re.S)
    assert match, "the benchmark step no longer embeds a python heredoc"
    return match.group(1)


def run_comparison(tmp_path: pathlib.Path, pairs) -> subprocess.CompletedProcess:
    """pairs: (package, target, native_gate, carrier_gate); None omits the key."""
    script = tmp_path / "compare.py"
    script.write_text(comparison_script(), encoding="utf-8")
    data = tmp_path / "benchmark"
    data.mkdir(exist_ok=True)
    for index, (package, target, native, carrier) in enumerate(pairs):
        for kind, verdict, prefix in (
                ("target-native", native, "n"), ("portable-carrier", carrier, "c")):
            row = {"kind": kind, "package": package, "target": target,
                   "architecture": "x86_64", "milliseconds": 10, "success": True}
            if verdict is not None:
                row["gate_success"] = verdict
            (data / f"{prefix}{index}.json").write_text(json.dumps(row))
    return subprocess.run([sys.executable, script.name], cwd=tmp_path,
                          capture_output=True, text=True)


# ---- structure: both arms must actually run the gate ----------------------

@pytest.mark.parametrize("job,gate_step,record_step", [
    ("native-package", "Run the existing native lint/install/smoke gate",
     "Record the portable arm's gate verdict"),
    ("native-baseline", "Run the same gate on the native arm",
     "Record the native arm's gate verdict"),
])
def test_each_arm_runs_the_gate_and_records_its_verdict(job, gate_step, record_step):
    gate = step(job, gate_step)
    assert gate.get("id") == "gate", f"{job}: the gate step needs an id to read"
    assert gate.get("continue-on-error") is True, (
        f"{job}: a red gate must be recorded, not fatal -- the parity check "
        "is what decides")
    assert "verify-package-factory-cell.sh" in gate["run"], job
    assert "gate_success" in step(job, record_step)["run"], job


@pytest.mark.parametrize("job", ["native-package", "native-baseline"])
def test_the_upload_comes_after_the_verdict_is_recorded(job):
    """Uploading first ships a row with no gate_success, which makes the
    parity check vacuous for that leg."""
    names = [s.get("name") or (s.get("uses") or "") for s in SPEC["jobs"][job]["steps"]]
    record = next(i for i, n in enumerate(names) if "gate verdict" in n)
    upload = next(i for i, n in enumerate(names)
                  if "upload-artifact" in n and i > record - 10)
    assert upload > record, (
        f"{job}: benchmark JSON is uploaded at step {upload}, before the "
        f"verdict is written at step {record}")


def test_the_result_job_requires_the_comparison():
    """Every per-leg gate is continue-on-error now, so if `result` did not
    require `benchmark`, the experiment could go green having compared
    nothing."""
    result = SPEC["jobs"]["result"]
    assert "benchmark" in result["needs"]
    body = step("result", "Require every experiment cell")["run"]
    assert 'test "$BENCHMARK" = success' in body, body


# ---- behaviour: the comparison itself -------------------------------------

def test_a_carrier_that_fails_where_native_passes_is_a_regression(tmp_path):
    done = run_comparison(tmp_path, [("uupd", "el10", True, False)])
    assert done.returncode != 0, done.stdout
    assert "REGRESSION" in done.stdout
    assert "uupd" in done.stdout


def test_both_arms_red_is_reported_and_not_fatal(tmp_path):
    """The dms/el10 shape: quickshell is unservable for either arm."""
    done = run_comparison(tmp_path, [("dms", "el10", False, False)])
    assert done.returncode == 0, done.stdout + done.stderr
    assert "red on BOTH arms" in done.stdout


def test_a_carrier_passing_where_native_fails_is_not_fatal(tmp_path):
    done = run_comparison(tmp_path, [("dms-cli", "opensuse-tumbleweed", False, True)])
    assert done.returncode == 0, done.stdout + done.stderr
    assert "portable passes where native fails" in done.stdout


def test_rows_without_a_verdict_fail_rather_than_pass_vacuously(tmp_path):
    """Guards the whole file: if gate_success ever stops being written, every
    test above would still pass against a comparison that compares nothing."""
    done = run_comparison(tmp_path, [("x", "el10", None, None)])
    assert done.returncode != 0, done.stdout
    assert "no gate_success" in done.stdout + done.stderr


def test_an_arm_with_no_counterpart_fails(tmp_path):
    script = tmp_path / "compare.py"
    script.write_text(comparison_script(), encoding="utf-8")
    data = tmp_path / "benchmark"
    data.mkdir()
    (data / "c.json").write_text(json.dumps({
        "kind": "portable-carrier", "package": "lonely", "target": "el10",
        "architecture": "x86_64", "milliseconds": 1, "success": True,
        "gate_success": True}))
    done = subprocess.run([sys.executable, script.name], cwd=tmp_path,
                          capture_output=True, text=True)
    assert done.returncode != 0
    assert "no arm-to-arm pair" in done.stdout + done.stderr
