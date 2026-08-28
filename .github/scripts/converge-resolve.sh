#!/usr/bin/env bash
# Resolve a convergence request into the two things every later wave needs:
# the build order that defines "everything", and the published indexes that
# define "served". Both come from the target contract via
# scripts/build_request.py -- never from this file, so adding a target is a
# contract block and not a workflow edit.
#
# env: REQUEST. Writes build_order and indexes to $GITHUB_OUTPUT.
set -euo pipefail
: "${REQUEST:?}" "${GITHUB_OUTPUT:?}"

python3 scripts/request.py "$REQUEST" --json /tmp/converge-plan.json
python3 - << 'PY' >> "$GITHUB_OUTPUT"
import json, os, sys
plan = json.load(open("/tmp/converge-plan.json"))
if plan["unmeasurable"]:
    sys.exit(f"::error::{plan['unmeasurable']}")
if not plan["build_order"]:
    sys.exit("::error::the request resolved to no build order")
urls = [
    url
    for arch in plan["architectures"]
    for url in plan["served_index"].get(arch, [])
]
if not urls:
    sys.exit(
        "::error::no published index for any architecture of "
        f"{plan['target']}; convergence is measured against the served "
        "index and cannot run without one"
    )
print(f"build_order={plan['build_order']}")
print("indexes=" + " ".join(urls))
PY
