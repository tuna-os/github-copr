#!/usr/bin/env bash
# Turn the residue into one blocker per root cause.
#
# The residue comes from converge-measurement.json -- the packages the
# PUBLISHED INDEX does not serve -- rather than from scraping a job log for
# "Failed packages". That matters twice: a failure whose line scrolled out of
# a truncated log is still in the residue, and so is a package no shard ever
# reached, which a log-scraper cannot see at all.
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
import json, os
m = json.load(open("converge-measurement.json"))
b = json.load(open("converge-blockers.json"))
request = os.environ["REQUEST"]
lines = [
    f"## Converge: {request}",
    "",
    f"**{m['verdict'].upper()}** — {m['why']}",
    "",
    f"- served: {m['served']}/{m['wanted']}",
    f"- remaining: {len(m['remaining'])}",
    f"- blockers: {b['blockers']} (plus {b['dependents']} dependent(s) that "
    "heal when their blocker does)",
    "",
]
if m["unreachable_indexes"]:
    lines += [
        "Indexes that could not be read, so `served` is a floor:",
        "",
    ] + [f"- {u['url']}: {u['error']}" for u in m["unreachable_indexes"]] + [""]
lines.append(open("/tmp/blockers.md").read())
open("converge-report.md", "w").write("\n".join(lines))
PY
cat converge-report.md >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
