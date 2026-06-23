#!/usr/bin/env bats
# BATS tests for scripts/build-local.sh — Local RPM builder using mock/podman

REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
BUILD_LOCAL="${REPO_ROOT}/scripts/build-local.sh"

@test "build-local.sh: exists" {
  run test -f "${BUILD_LOCAL}"
  [ "$status" -eq 0 ]
}

@test "build-local.sh: has bash shebang" {
  run head -1 "${BUILD_LOCAL}"
  [[ "$output" =~ ^#!/.*bash ]]
}

@test "build-local.sh: has set -euo pipefail" {
  run grep 'set -euo pipefail' "${BUILD_LOCAL}"
  [ "$status" -eq 0 ]
}

@test "build-local.sh: prints usage when called with no arguments" {
  run bash "${BUILD_LOCAL}"
  [ "$status" -ne 0 ]
  [[ "$output" =~ Usage ]] || [[ "$output" =~ usage ]]
}

@test "build-local.sh: defines SCRIPT_DIR" {
  run grep 'SCRIPT_DIR=' "${BUILD_LOCAL}"
  [ "$status" -eq 0 ]
}

@test "build-local.sh: references PROJECT_DIR" {
  run grep 'PROJECT_DIR=' "${BUILD_LOCAL}"
  [ "$status" -eq 0 ]
}

@test "build-local.sh: passes shellcheck" {
  if command -v shellcheck &>/dev/null; then
    run shellcheck "${BUILD_LOCAL}"
    [ "$status" -eq 0 ]
  else
    skip "shellcheck not installed"
  fi
}
