#!/usr/bin/env bash
# Turn the residue into one blocker per root cause, led by the stage that
# decides.
#
# The residue comes from converge-measurement.json -- the packages the
# PUBLISHED INDEX does not serve -- rather than from scraping a job log for
# "Failed packages". That matters twice: a failure whose line scrolled out of a
# truncated log is still in the residue, and so is a package no shard ever
# reached, which a log-scraper cannot see at all.
#
# The OPEN STAGE is reported first and separately. A report that listed 101
# unserved packages in one flat block would bury the seven that decide whether
# an image can boot at all under ninety-four that cannot matter until those
# seven land.
#
# env: REQUEST. Reads converge-measurement.json and waves/failure-logs/.
set -euo pipefail
: "${REQUEST:?}"

python3 -c "
import json
data = json.load(open('converge-measurement.json'))
print('\n'.join(data['remaining']))
" > /tmp/converge-remaining.txt

logs_arg=()
if [[ -d waves/failure-logs ]]; then
    logs_arg=(--failure-logs waves/failure-logs)
fi

python3 scripts/classify-chain-failures.py \
    --packages /tmp/converge-remaining.txt \
    "${logs_arg[@]}" \
    --json converge-blockers.json \
    --markdown /tmp/blockers.md

python3 - << 'PY'
import json, os, sys
sys.path.insert(0, "scripts")
import stack_readiness

m = json.load(open("converge-measurement.json"))
b = json.load(open("converge-blockers.json"))
request = os.environ["REQUEST"]

lines = [
    f"## Converge: {request}",
    "",
    f"**{m['verdict'].upper()}** — {m['why']}",
    "",
    "| stage | served | remaining | why it matters |",
    "| --- | --- | --- | --- |",
]
for stage in m["stages"]:
    lines.append(
        f"| `{stage['name']}` | {stage['served']}/{stage['wanted']} | "
        f"{len(stage['remaining'])} | "
        f"{stack_readiness.STAGE_WHY[stage['name']]} |"
    )
lines.append("")

if m["open_stage"]:
    stage = next(s for s in m["stages"] if s["name"] == m["open_stage"])
    lines += [
        f"### Open stage: `{m['open_stage']}`",
        "",
        "Nothing later can matter until these are served:",
        "",
        "".join(f"- `{n}`\n" for n in stage["remaining"]),
    ]
else:
    lines += [
        "Every package the stack needs is served. The remaining question is "
        "whether it BOOTS, which only tunaOS's Gate can answer:",
        "",
        "```",
        "gh workflow run \"Build Hummingbird\" -R tuna-os/tunaos -f flavor=gnome",
        "```",
        "",
        "Green is `.github/green-criteria.yml`'s composite: builds, ships the "
        "declared desktop, and boots under QEMU with "
        "TUNAOS_DESKTOP_CONTRACT_OK on the serial console.",
        "",
    ]

if m["unreachable_indexes"]:
    lines += ["Indexes that could not be read, so `served` is a floor:", ""]
    lines += [f"- {u['url']}: {u['error']}" for u in m["unreachable_indexes"]]
    lines += [""]

lines += [
    f"### Blockers ({b['blockers']}, plus {b['dependents']} dependent(s) that "
    "heal when their blocker does)",
    "",
    open("/tmp/blockers.md").read(),
]
open("converge-report.md", "w").write("\n".join(lines))
PY
cat converge-report.md >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
