#!/usr/bin/env bats
# BATS tests for scripts/build-chain.sh — RPM Build Chain Engine
#
# build-chain.sh requires a build-order.yml, RPM build tools, and either
# podman or mock. These tests validate structure, argument parsing, and
# error handling without running an actual build.

REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
BUILD_CHAIN="${REPO_ROOT}/scripts/build-chain.sh"

@test "build-chain.sh: exists and is executable" {
  run test -x "${BUILD_CHAIN}"
  [ "$status" -eq 0 ]
}

@test "build-chain.sh: has bash shebang" {
  run head -1 "${BUILD_CHAIN}"
  [[ "$output" =~ ^#!/.*bash ]]
}

@test "build-chain.sh: shows usage with --help" {
  run bash "${BUILD_CHAIN}" --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ Usage ]]
}

@test "build-chain.sh: shows usage with --manifest without file" {
  run bash "${BUILD_CHAIN}" --manifest
  [ "$status" -ne 0 ]
}

@test "build-chain.sh: references build-order.yml in default operation" {
  run bash "${BUILD_CHAIN}" --backend podman --dry-run 2>&1 || true
  # Should mention build-order.yml or fail gracefully about missing tools
  [[ "$output" =~ build-order ]] || [[ "$output" =~ manifest ]]
}

@test "build-chain.sh: passes shellcheck" {
  if command -v shellcheck &>/dev/null; then
    run shellcheck "${BUILD_CHAIN}"
    [ "$status" -eq 0 ]
  else
    skip "shellcheck not installed"
  fi
}
