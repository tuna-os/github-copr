#!/usr/bin/env bash
# One convergence measurement, against the ordered stages a working stack
# needs -- contract, then session, then the tail. See
# scripts/stack_readiness.py for why a flat served-vs-wanted count over the
# build order is the wrong objective.
#
# env: REQUEST, WAVE, MAX_WAVES, and (from wave 2 on) PREVIOUS_STAGE and
#      PREVIOUS_REMAINING -- the OPEN STAGE the previous wave reported and its
#      count, not the whole-order total.
set -euo pipefail
: "${REQUEST:?}" "${WAVE:?}" "${MAX_WAVES:?}"

args=(--request "$REQUEST" --wave "$WAVE" --max-waves "$MAX_WAVES"
      --report-json converge-measurement.json)
# Unset rather than empty: the planner distinguishes "no previous wave" (first
# wave, always continue) from "the previous wave left N in this stage", and an
# empty string would make wave 1 look like a wave that already ran.
if [[ -n "${PREVIOUS_STAGE:-}" && -n "${PREVIOUS_REMAINING:-}" ]]; then
    args+=(--previous-stage "$PREVIOUS_STAGE"
           --previous-remaining "$PREVIOUS_REMAINING")
fi
python3 scripts/plan-converge.py "${args[@]}"
