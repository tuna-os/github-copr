#!/usr/bin/env bash
# One convergence measurement: how much of the build order the published
# index now serves, and what that means for the next wave.
#
# env: BUILD_ORDER, INDEXES (space-separated URLs), WAVE, MAX_WAVES,
#      PREVIOUS_REMAINING (empty on the first wave).
set -euo pipefail
: "${BUILD_ORDER:?}" "${INDEXES:?}" "${WAVE:?}" "${MAX_WAVES:?}"

args=(--build-order "$BUILD_ORDER" --wave "$WAVE" --max-waves "$MAX_WAVES"
      --report-json converge-measurement.json)
# read -ra rather than an unquoted loop: INDEXES is a space-separated list
# by construction (converge-resolve.sh joins it), and relying on unquoted
# word splitting would also glob.
read -ra _urls <<< "$INDEXES"
for url in "${_urls[@]}"; do
    args+=(--served-index "$url")
done
# Unset rather than empty: the planner distinguishes "no previous wave"
# (first wave, always continue) from "the previous wave left N", and passing
# an empty string would make the first wave look like a zero-remaining one.
if [[ -n "${PREVIOUS_REMAINING:-}" ]]; then
    args+=(--previous-remaining "$PREVIOUS_REMAINING")
fi
python3 scripts/plan-converge.py "${args[@]}"
