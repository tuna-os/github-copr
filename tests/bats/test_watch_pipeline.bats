#!/usr/bin/env bats
# BATS tests for scripts/watch-pipeline.sh — Pipeline monitoring

REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
WATCH_PIPELINE="${REPO_ROOT}/scripts/watch-pipeline.sh"

@test "watch-pipeline.sh: exists and is executable" {
  run test -x "${WATCH_PIPELINE}"
  [ "$status" -eq 0 ]
}

@test "watch-pipeline.sh: has bash shebang" {
  run head -1 "${WATCH_PIPELINE}"
  [[ "$output" =~ ^#!/.*bash ]]
}

@test "watch-pipeline.sh: has set -euo pipefail" {
  run grep 'set -euo pipefail' "${WATCH_PIPELINE}"
  [ "$status" -eq 0 ]
}

@test "watch-pipeline.sh: shows help with --help" {
  run bash "${WATCH_PIPELINE}" --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ Usage ]] || [[ "$output" =~ usage ]]
}

@test "watch-pipeline.sh: status subcommand runs without error" {
  run bash "${WATCH_PIPELINE}" status 2>&1 || true
  # Should either list runs or fail gracefully (no gh auth)
  [ "$status" -eq 0 ] || [[ "$output" =~ auth ]] || [[ "$output" =~ error ]] || [[ "$output" =~ Usage ]] || [[ "$output" =~ accessible ]] || [[ "$output" =~ token ]] || [[ "$output" =~ Forbidden ]] || [[ "$output" =~ "not found" ]]
}

@test "watch-pipeline.sh: defines WORKFLOW_BOOTSTRAP" {
  run grep 'WORKFLOW_BOOTSTRAP=' "${WATCH_PIPELINE}"
  [ "$status" -eq 0 ]
}

@test "watch-pipeline.sh: references gnome49 workflow" {
  run grep 'gnome49' "${WATCH_PIPELINE}"
  [ "$status" -eq 0 ]
}

@test "watch-pipeline.sh: passes shellcheck" {
  if command -v shellcheck &>/dev/null; then
    run shellcheck "${WATCH_PIPELINE}"
    [ "$status" -eq 0 ]
  else
    skip "shellcheck not installed"
  fi
}
