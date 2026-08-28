#!/usr/bin/env bash
# Validate a convergence request before any wave is dispatched.
#
# plan-converge.py resolves the request itself, so nothing needs to be threaded
# through the workflow. What this does is FAIL EARLY and legibly on the two
# asks that cannot converge at all: a target whose contract declares no
# gap_measurement (its build order is hand-curated), and one with no published
# index (convergence is measured against the served index).
#
# env: REQUEST.
set -euo pipefail
: "${REQUEST:?}"

python3 scripts/request.py "$REQUEST" --json /tmp/converge-plan.json
python3 - << 'PY'
import json, sys
plan = json.load(open("/tmp/converge-plan.json"))
if plan["unmeasurable"]:
    sys.exit(f"::error::{plan['unmeasurable']}")
if not plan["build_order"]:
    sys.exit("::error::the request resolved to no build order")
if not any(plan["served_index"].get(a) for a in plan["architectures"]):
    sys.exit(
        "::error::no published index for any architecture of "
        f"{plan['target']}; convergence is measured against the served "
        "index and cannot run without one"
    )
PY
