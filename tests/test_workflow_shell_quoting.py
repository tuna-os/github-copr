"""Single-quoted docker scripts must not contain apostrophes.

Measured failure (PR #419, waves 2 and 3): a comment inside a
`bash -lc '...'` docker script said "tunaOS#1833's" — the apostrophe closed
the single-quoted argument early, so every line after it (including the
`apt-get build-dep` under test) executed on the RUNNER instead of in the
container, and two full CI waves failed with errors that looked like apt
CLI problems. The YAML parses, shellcheck never sees the workflow, and the
script is syntactically valid in both halves — only runtime behavior shows
the break. This test is the only guard that can catch it before a push.
"""
from __future__ import annotations

import pathlib

import yaml

WORKFLOWS = (pathlib.Path(__file__).resolve().parents[1] / ".github" /
             "workflows")

OPENER = "bash -lc '"


def test_single_quoted_docker_scripts_contain_no_apostrophe() -> None:
    checked = 0
    for wf_path in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
        for jname, job in (doc.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                run = step.get("run") or ""
                start = 0
                while True:
                    i = run.find(OPENER, start)
                    if i == -1:
                        break
                    rest = run[i + len(OPENER):]
                    end = rest.rfind("'")
                    assert end != -1, (wf_path.name, jname, "unterminated")
                    inner = rest[:end]
                    assert "'" not in inner, (
                        f"{wf_path.name} job {jname}: apostrophe inside a "
                        f"single-quoted docker script near "
                        f"...{inner[max(0, inner.find(chr(39)) - 60):inner.find(chr(39)) + 5]!r} — "
                        f"it ends the quoted argument and runs the rest of "
                        f"the script on the runner (PR #419 waves 2-3)")
                    checked += 1
                    start = i + len(OPENER) + end
    assert checked >= 4, f"only {checked} scripts found — glob broke?"
